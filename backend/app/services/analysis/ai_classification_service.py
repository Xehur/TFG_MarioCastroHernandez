"""
Servicio de clasificación de tejido por IA (Sprint 7).

Ejecuta un modelo de deep learning pre-entrenado (ResNet18 de TIAToolbox sobre
el dataset NCT-CRC-HE-100K / "kather100k", CC-BY-4.0) para clasificar el tejido
de una WSI (o de una región anotada) en 9 categorías histológicas, y las agrupa
en las categorías de alto nivel de interés (tumoral, estroma, no tumoral,
necrosis, fondo).

Estrategia (memoria y CPU contenidas):
- Se trabaja sobre una miniatura (imagen completa) o la región de la anotación,
  igual que la detección de tejido / mapa de densidades, para no cargar la WSI
  entera en memoria.
- La imagen se divide en una rejilla de celdas; cada celda con suficiente tejido
  (según la máscara de tejido clásica) se redimensiona a 224x224 y se clasifica
  en lotes. Las celdas de fondo se etiquetan como "BACK" sin inferencia.
- Se genera un overlay RGBA (mapa de clases) coloreado por celda y un resumen de
  distribución por clase y por grupo, cacheados en disco/BD.

Nota sobre magnificación: el modelo se entrenó con parches de 224x224 a
~0.5 µm/px (20x). Para respetar esa escala, cada celda de la rejilla se
clasifica leyendo un parche REAL de 224x224 a 0.5 MPP desde la WSI (nivel de
pirámide adecuado), en lugar de aplastar una miniatura. Así los resultados son
consistentes entre la imagen completa y una región anotada, y coinciden con la
distribución de entrenamiento del modelo. Si la imagen es muy grande, se acota
el número de parches muestreando celdas representativas (manteniendo siempre la
magnificación correcta).

El modelo se carga de forma perezosa y se cachea en memoria (proceso).
"""
from __future__ import annotations

import os
import math
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import AnalysisResult
from app.models.annotation import Annotation
from app.services.analysis.tissue_detection import detect_tissue
from app.services.analysis.annotation_analysis_service import (
    annotation_bbox,
    _shape_mask,
)
from app.services.wsi.openslide_service import OpenSlideService

logger = logging.getLogger(__name__)

AI_ANALYSIS_TYPE = "ai_classification"
MODEL_ID = "hf-hub:1aurent/resnet18.tiatoolbox-kather100k"
MODEL_INPUT_SIZE = 224
DEFAULT_MAX_PATCHES = 196
DEFAULT_MIN_TISSUE_FRAC = 0.35
_THUMBNAIL_MAX_SIZE = 2048
_BATCH_SIZE = 32

# Magnificación objetivo del modelo (µm/px). kather100k se entrenó a ~0.5 MPP.
TARGET_MPP = 0.5
# MPP por defecto si la WSI no expone metadatos de magnificación.
DEFAULT_MPP = 0.5

# Orden EXACTO de las clases del modelo (config.json del repo HF).
CLASS_CODES: List[str] = ["BACK", "NORM", "DEB", "TUM", "ADI", "MUC", "MUS", "STR", "LYM"]

# Metadatos por clase: nombre en español, grupo de alto nivel y color RGB.
CLASS_META: Dict[str, Dict[str, Any]] = {
    "BACK": {"name": "Fondo", "group": "Fondo", "color": [148, 163, 184]},
    "NORM": {"name": "Mucosa normal", "group": "No tumoral", "color": [34, 197, 94]},
    "DEB": {"name": "Debris / Necrosis", "group": "Necrosis", "color": [120, 53, 15]},
    "TUM": {"name": "Tumoral", "group": "Tumoral", "color": [220, 38, 38]},
    "ADI": {"name": "Tejido adiposo", "group": "No tumoral", "color": [96, 165, 250]},
    "MUC": {"name": "Moco", "group": "No tumoral", "color": [45, 212, 191]},
    "MUS": {"name": "Músculo liso", "group": "No tumoral", "color": [236, 72, 153]},
    "STR": {"name": "Estroma", "group": "Estroma", "color": [245, 158, 11]},
    "LYM": {"name": "Linfocitos", "group": "No tumoral", "color": [139, 92, 246]},
}

# Orden de presentación de los grupos de alto nivel.
GROUP_ORDER: List[str] = ["Tumoral", "Estroma", "No tumoral", "Necrosis", "Fondo"]

# Color RGB por grupo de alto nivel. El overlay, la leyenda y las barras usan
# SIEMPRE estos colores para que lo que se pinta sobre la imagen coincida con la
# leyenda (las 5 categorías), en lugar del color de cada clase fina.
GROUP_COLORS: Dict[str, List[int]] = {
    "Tumoral": [220, 38, 38],
    "Estroma": [245, 158, 11],
    "No tumoral": [34, 197, 94],
    "Necrosis": [120, 53, 15],
    "Fondo": [148, 163, 184],
}

_model = None
_model_lock = threading.Lock()


# --- Modelo ------------------------------------------------------------------

def get_model():
    """Carga (perezosamente) y cachea el modelo timm en CPU, en modo eval."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import torch  # import diferido: solo si se usa la IA
                import timm

                logger.info("Cargando modelo de clasificación IA: %s", MODEL_ID)
                model = timm.create_model(MODEL_ID, pretrained=True)
                model.eval()
                torch.set_grad_enabled(False)
                _model = model
    return _model


def class_legend() -> List[Dict[str, Any]]:
    """Leyenda (código, nombre, grupo, color) de todas las clases del modelo."""
    return [
        {
            "code": code,
            "name": CLASS_META[code]["name"],
            "group": CLASS_META[code]["group"],
            "color": CLASS_META[code]["color"],
        }
        for code in CLASS_CODES
    ]


def _grid_shape(width: int, height: int, max_patches: int) -> Tuple[int, int]:
    """Número de columnas y filas de la rejilla, proporcional al aspecto."""
    width = max(1, width)
    height = max(1, height)
    aspect = width / height
    cols = max(1, min(width, int(round(math.sqrt(max_patches * aspect)))))
    rows = max(1, min(height, int(round(max_patches / cols))))
    return cols, rows


def classify_rgb(
    rgb: np.ndarray,
    tissue_mask: Optional[np.ndarray] = None,
    *,
    max_patches: int = DEFAULT_MAX_PATCHES,
    min_tissue_frac: float = DEFAULT_MIN_TISSUE_FRAC,
) -> Dict[str, Any]:
    """
    Clasifica el tejido de una imagen RGB por celdas.

    Devuelve un diccionario con la matriz de etiquetas (índice de clase por
    celda; -1 = fondo/ignorada), confianzas, recuentos por clase y overlay RGBA.
    """
    import torch

    if rgb.ndim == 2:
        rgb = np.stack([rgb] * 3, axis=-1)
    if rgb.shape[-1] == 4:
        rgb = rgb[..., :3]
    rgb = np.ascontiguousarray(rgb.astype(np.uint8))

    height, width = rgb.shape[0], rgb.shape[1]
    cols, rows = _grid_shape(width, height, max_patches)

    labels = np.full((rows, cols), -1, dtype=np.int64)
    confid = np.zeros((rows, cols), dtype=np.float32)

    # Bordes enteros de las celdas.
    x_edges = np.linspace(0, width, cols + 1).round().astype(int)
    y_edges = np.linspace(0, height, rows + 1).round().astype(int)

    patches: List[np.ndarray] = []
    positions: List[Tuple[int, int]] = []

    for r in range(rows):
        y0, y1 = y_edges[r], max(y_edges[r] + 1, y_edges[r + 1])
        for c in range(cols):
            x0, x1 = x_edges[c], max(x_edges[c] + 1, x_edges[c + 1])
            cell = rgb[y0:y1, x0:x1]
            if tissue_mask is not None:
                frac = float(tissue_mask[y0:y1, x0:x1].mean())
                if frac < min_tissue_frac:
                    continue  # celda de fondo: se deja como -1
            pil = PILImage.fromarray(cell, mode="RGB").resize(
                (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), PILImage.BICUBIC
            )
            patches.append(np.asarray(pil, dtype=np.float32) / 255.0)
            positions.append((r, c))

    counts = {code: 0 for code in CLASS_CODES}

    if patches:
        model = get_model()
        preds: List[int] = []
        probs: List[float] = []
        with torch.no_grad():
            for i in range(0, len(patches), _BATCH_SIZE):
                batch = np.stack(patches[i : i + _BATCH_SIZE])  # (n,224,224,3)
                tensor = torch.from_numpy(batch).permute(0, 3, 1, 2).contiguous()
                logits = model(tensor)
                sm = torch.softmax(logits, dim=1)
                conf, idx = sm.max(dim=1)
                preds.extend(idx.tolist())
                probs.extend(conf.tolist())

        for (r, c), cls_idx, conf in zip(positions, preds, probs):
            labels[r, c] = cls_idx
            confid[r, c] = conf
            counts[CLASS_CODES[cls_idx]] += 1

    overlay = _labels_to_overlay(labels, x_edges, y_edges, width, height)

    tissue_patches = int((labels >= 0).sum())
    total_patches = rows * cols

    return {
        "labels": labels.tolist(),
        "rows": rows,
        "cols": cols,
        "counts": counts,
        "tissue_patches": tissue_patches,
        "total_patches": total_patches,
        "mean_confidence": float(confid[labels >= 0].mean()) if tissue_patches else 0.0,
        "overlay": overlay,
    }


def classify_slide_region(
    slide: "OpenSlideService",
    region_bbox: Tuple[int, int, int, int],
    thumb_rgb: np.ndarray,
    tissue_mask: Optional[np.ndarray],
    *,
    max_patches: int = DEFAULT_MAX_PATCHES,
    min_tissue_frac: float = DEFAULT_MIN_TISSUE_FRAC,
) -> Dict[str, Any]:
    """
    Clasifica una región de la WSI leyendo parches REALES a la magnificación
    del modelo (224x224 @ ~0.5 MPP), en lugar de aplastar una miniatura.

    Args:
        slide: servicio OpenSlide abierto sobre la WSI.
        region_bbox: (x0, y0, w, h) de la región a clasificar, en px de nivel 0
            (imagen completa: (0, 0, W, H); anotación: su bounding box).
        thumb_rgb: miniatura de la región (para el gating de tejido y para fijar
            la resolución del overlay, alineado con la imagen base).
        tissue_mask: máscara booleana de tejido en la resolución de ``thumb_rgb``.
        max_patches: cota superior de parches clasificados (acota el cómputo en
            imágenes grandes muestreando celdas representativas).
        min_tissue_frac: fracción mínima de tejido de una celda para clasificarla.

    Devuelve el mismo formato que ``classify_rgb`` (labels, overlay a resolución
    de ``thumb_rgb``, recuentos, etc.), más metadatos de magnificación.
    """
    import torch

    x0, y0, region_w, region_h = region_bbox
    thumb_h, thumb_w = thumb_rgb.shape[0], thumb_rgb.shape[1]

    # Tamaño del parche en px de nivel 0 para alcanzar la magnificación objetivo.
    mpp = slide.get_mpp_x() or DEFAULT_MPP
    target_ds = TARGET_MPP / mpp
    patch_px = max(1, int(round(MODEL_INPUT_SIZE * target_ds)))

    # Rejilla de celdas: si el muestreo denso (una celda por parche) supera
    # ``max_patches``, se usa una zancada para acotar el cómputo. Cada celda se
    # representa por un parche REAL de 224px @ 0.5 MPP leído de su centro.
    dense_cols = max(1, int(math.ceil(region_w / patch_px)))
    dense_rows = max(1, int(math.ceil(region_h / patch_px)))
    stride = max(
        1, int(math.ceil(math.sqrt((dense_cols * dense_rows) / max(1, max_patches))))
    )
    cols = max(1, int(round(dense_cols / stride)))
    rows = max(1, int(round(dense_rows / stride)))

    labels = np.full((rows, cols), -1, dtype=np.int64)
    confid = np.zeros((rows, cols), dtype=np.float32)

    # Bordes de celda en coords de nivel 0 (dentro de la región) y en la miniatura.
    x_edges0 = np.linspace(0, region_w, cols + 1).round().astype(int)
    y_edges0 = np.linspace(0, region_h, rows + 1).round().astype(int)
    tx_edges = np.linspace(0, thumb_w, cols + 1).round().astype(int)
    ty_edges = np.linspace(0, thumb_h, rows + 1).round().astype(int)

    patches: List[np.ndarray] = []
    positions: List[Tuple[int, int]] = []

    for r in range(rows):
        ty0, ty1 = ty_edges[r], max(ty_edges[r] + 1, ty_edges[r + 1])
        for c in range(cols):
            tx0, tx1 = tx_edges[c], max(tx_edges[c] + 1, tx_edges[c + 1])
            if tissue_mask is not None:
                frac = float(tissue_mask[ty0:ty1, tx0:tx1].mean())
                if frac < min_tissue_frac:
                    continue  # celda de fondo: se deja como -1

            # Centro de la celda en coordenadas absolutas de nivel 0.
            cx = x0 + (int(x_edges0[c]) + int(x_edges0[c + 1])) / 2.0
            cy = y0 + (int(y_edges0[r]) + int(y_edges0[r + 1])) / 2.0

            patch = slide.read_patch_rgb(cx, cy, patch_px, out_size=MODEL_INPUT_SIZE)
            patches.append(np.asarray(patch, dtype=np.float32) / 255.0)
            positions.append((r, c))

    counts = {code: 0 for code in CLASS_CODES}

    if patches:
        model = get_model()
        preds: List[int] = []
        probs: List[float] = []
        with torch.no_grad():
            for i in range(0, len(patches), _BATCH_SIZE):
                batch = np.stack(patches[i : i + _BATCH_SIZE])
                tensor = torch.from_numpy(batch).permute(0, 3, 1, 2).contiguous()
                logits = model(tensor)
                sm = torch.softmax(logits, dim=1)
                conf, idx = sm.max(dim=1)
                preds.extend(idx.tolist())
                probs.extend(conf.tolist())

        for (r, c), cls_idx, conf in zip(positions, preds, probs):
            labels[r, c] = cls_idx
            confid[r, c] = conf
            counts[CLASS_CODES[cls_idx]] += 1

    overlay = _labels_to_overlay(labels, tx_edges, ty_edges, thumb_w, thumb_h)

    tissue_patches = int((labels >= 0).sum())
    total_patches = rows * cols

    return {
        "labels": labels.tolist(),
        "rows": rows,
        "cols": cols,
        "counts": counts,
        "tissue_patches": tissue_patches,
        "total_patches": total_patches,
        "mean_confidence": float(confid[labels >= 0].mean()) if tissue_patches else 0.0,
        "overlay": overlay,
        "mpp": round(float(mpp), 4),
        "patch_px_level0": patch_px,
    }


def _labels_to_overlay(
    labels: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    width: int,
    height: int,
    alpha: int = 140,
) -> np.ndarray:
    """Colorea cada celda según el GRUPO de su clase en una imagen RGBA
    (H, W, 4), para que el overlay coincida con la leyenda de 5 categorías."""
    overlay = np.zeros((height, width, 4), dtype=np.uint8)
    rows, cols = labels.shape
    for r in range(rows):
        y0, y1 = y_edges[r], y_edges[r + 1]
        for c in range(cols):
            cls_idx = labels[r, c]
            if cls_idx < 0:
                continue
            code = CLASS_CODES[cls_idx]
            group = CLASS_META[code]["group"]
            if group == "Fondo":
                continue  # el fondo no se pinta
            x0, x1 = x_edges[c], x_edges[c + 1]
            color = GROUP_COLORS[group]
            overlay[y0:y1, x0:x1, 0] = color[0]
            overlay[y0:y1, x0:x1, 1] = color[1]
            overlay[y0:y1, x0:x1, 2] = color[2]
            overlay[y0:y1, x0:x1, 3] = alpha
    return overlay


# --- Resumen (distribución por clase y grupo) --------------------------------

def _build_summary(counts: Dict[str, int]) -> Dict[str, Any]:
    """Compone la distribución por clase y por grupo (excluyendo el fondo)."""
    tissue_total = sum(v for code, v in counts.items() if code != "BACK")
    tissue_total = tissue_total or 0

    classes: List[Dict[str, Any]] = []
    for code in CLASS_CODES:
        if code == "BACK":
            continue
        count = counts.get(code, 0)
        percent = round(100.0 * count / tissue_total, 2) if tissue_total else 0.0
        meta = CLASS_META[code]
        classes.append(
            {
                "code": code,
                "name": meta["name"],
                "group": meta["group"],
                "color": meta["color"],
                "group_color": GROUP_COLORS[meta["group"]],
                "count": count,
                "percent": percent,
            }
        )

    group_counts: Dict[str, int] = {g: 0 for g in GROUP_ORDER}
    for code in CLASS_CODES:
        if code == "BACK":
            continue
        meta = CLASS_META[code]
        group_counts[meta["group"]] += counts.get(code, 0)

    groups: List[Dict[str, Any]] = []
    for g in GROUP_ORDER:
        if g == "Fondo":
            continue
        count = group_counts.get(g, 0)
        percent = round(100.0 * count / tissue_total, 2) if tissue_total else 0.0
        groups.append(
            {
                "group": g,
                "color": GROUP_COLORS[g],
                "count": count,
                "percent": percent,
            }
        )

    dominant_class = max(classes, key=lambda c: c["count"], default=None)
    dominant_group = max(groups, key=lambda g: g["count"], default=None)

    return {
        "classes": classes,
        "groups": groups,
        "tissue_patches": tissue_total,
        "dominant_class": dominant_class["code"] if dominant_class and tissue_total else None,
        "dominant_group": dominant_group["group"] if dominant_group and tissue_total else None,
    }


def _model_info() -> Dict[str, Any]:
    return {
        "id": "1aurent/resnet18.tiatoolbox-kather100k",
        "arch": "resnet18",
        "dataset": "NCT-CRC-HE-100K",
        "license": "CC-BY-4.0",
    }


# --- Rutas de caché en disco -------------------------------------------------

def _image_dir(image_id: int) -> str:
    path = os.path.join(settings.UPLOAD_DIR, "analysis", str(image_id))
    os.makedirs(path, exist_ok=True)
    return path


def _annotation_dir(image_id: int, annotation_id: int) -> str:
    path = os.path.join(
        settings.UPLOAD_DIR, "analysis", str(image_id), f"ann_{annotation_id}"
    )
    os.makedirs(path, exist_ok=True)
    return path


# --- Núcleo compartido -------------------------------------------------------

def _run_and_store(
    db: Session,
    image_id: int,
    annotation_id: Optional[int],
    slide: "OpenSlideService",
    region_bbox: Tuple[int, int, int, int],
    thumb_rgb: np.ndarray,
    png_path: str,
    extra: Optional[Dict[str, Any]] = None,
) -> AnalysisResult:
    """Clasifica la región (parches reales a 0.5 MPP), guarda el overlay PNG y
    persiste el AnalysisResult."""
    tissue = detect_tissue(thumb_rgb)
    result = classify_slide_region(slide, region_bbox, thumb_rgb, tissue.mask)

    PILImage.fromarray(result["overlay"], mode="RGBA").save(png_path, format="PNG")

    summary = _build_summary(result["counts"])
    data: Dict[str, Any] = {
        "type": AI_ANALYSIS_TYPE,
        "model": _model_info(),
        "map_path": png_path,
        "rows": result["rows"],
        "cols": result["cols"],
        "grid": result["labels"],
        "total_patches": result["total_patches"],
        "tissue_percent": round(tissue.tissue_percent, 4),
        "mean_confidence": round(result["mean_confidence"], 4),
        "mpp": result.get("mpp"),
        "legend": class_legend(),
        **summary,
    }
    if extra:
        data.update(extra)

    existing = _get_cached(db, image_id, annotation_id)
    if existing is not None:
        existing.result_data = data
        db.commit()
        db.refresh(existing)
        return existing

    analysis = AnalysisResult(
        image_id=image_id,
        annotation_id=annotation_id,
        analysis_type=AI_ANALYSIS_TYPE,
        result_data=data,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def _get_cached(
    db: Session, image_id: int, annotation_id: Optional[int]
) -> Optional[AnalysisResult]:
    query = db.query(AnalysisResult).filter(
        AnalysisResult.analysis_type == AI_ANALYSIS_TYPE
    )
    if annotation_id is None:
        query = query.filter(
            AnalysisResult.image_id == image_id,
            AnalysisResult.annotation_id.is_(None),
        )
    else:
        query = query.filter(AnalysisResult.annotation_id == annotation_id)
    return query.order_by(AnalysisResult.created_at.desc()).first()


def load_map_png_bytes(analysis: AnalysisResult) -> bytes:
    map_path = (analysis.result_data or {}).get("map_path")
    if not map_path or not os.path.exists(map_path):
        raise FileNotFoundError("PNG de clasificación IA no encontrado")
    with open(map_path, "rb") as fh:
        return fh.read()


# --- Ámbito imagen -----------------------------------------------------------

def get_cached_image_classification(
    db: Session, image_id: int
) -> Optional[AnalysisResult]:
    return _get_cached(db, image_id, None)


def generate_image_classification(
    db: Session, image_id: int, file_path: str, max_size: int = _THUMBNAIL_MAX_SIZE
) -> AnalysisResult:
    slide = OpenSlideService(file_path)
    try:
        rgb, scale = slide.get_thumbnail_rgb(max_size=max_size)
        thumb_h, thumb_w = rgb.shape[0], rgb.shape[1]
        region_bbox = (0, 0, int(round(thumb_w * scale)), int(round(thumb_h * scale)))
        png_path = os.path.join(_image_dir(image_id), "ai_classification.png")
        return _run_and_store(
            db, image_id, None, slide, region_bbox, rgb, png_path,
            extra={"scale": scale},
        )
    finally:
        slide.close()


def get_or_create_image_classification(
    db: Session, image_id: int, file_path: str, force: bool = False
) -> AnalysisResult:
    if not force:
        cached = get_cached_image_classification(db, image_id)
        if cached is not None:
            map_path = (cached.result_data or {}).get("map_path")
            if map_path and os.path.exists(map_path):
                return cached
    return generate_image_classification(db, image_id, file_path)


# --- Ámbito anotación --------------------------------------------------------

def get_cached_annotation_classification(
    db: Session, annotation_id: int
) -> Optional[AnalysisResult]:
    return _get_cached(db, 0, annotation_id)


def generate_annotation_classification(
    db: Session, annotation: Annotation, file_path: str
) -> AnalysisResult:
    bbox = annotation_bbox(annotation.shape_type, annotation.coordinates or {})
    slide = OpenSlideService(file_path)
    try:
        rgb, scale, used_bbox = slide.read_region_rgb(*bbox, max_size=_THUMBNAIL_MAX_SIZE)
        # Para formas no rectangulares, excluye (a blanco) los píxeles fuera de
        # la forma para que el gating de tejido no clasifique fuera de la región.
        shape_mask = _shape_mask(
            annotation.shape_type,
            annotation.coordinates or {},
            used_bbox,
            rgb.shape[1],
            rgb.shape[0],
            scale,
        )
        if shape_mask is not None:
            rgb = rgb.copy()
            rgb[~shape_mask] = 255
        png_path = os.path.join(
            _annotation_dir(annotation.image_id, annotation.id), "ai_classification.png"
        )
        return _run_and_store(
            db,
            annotation.image_id,
            annotation.id,
            slide,
            used_bbox,
            rgb,
            png_path,
            extra={"scale": scale, "bbox": list(used_bbox)},
        )
    finally:
        slide.close()


def get_or_create_annotation_classification(
    db: Session, annotation: Annotation, file_path: str, force: bool = False
) -> AnalysisResult:
    if not force:
        cached = get_cached_annotation_classification(db, annotation.id)
        if cached is not None:
            map_path = (cached.result_data or {}).get("map_path")
            if map_path and os.path.exists(map_path):
                return cached
    return generate_annotation_classification(db, annotation, file_path)
