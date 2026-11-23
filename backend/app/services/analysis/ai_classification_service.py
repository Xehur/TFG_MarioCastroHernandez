"""
Servicio de clasificación de tejido por IA.

Ejecuta el modelo InceptionV3 entrenado sobre tejido mamario H&E (dataset BACH /
ICIAR 2018) para clasificar el tejido de una WSI (o de una región anotada) en 4
categorías: Normal, Benigno, Carcinoma in situ y Carcinoma invasivo. Las celdas
sin tejido suficiente se marcan como "Fondo / no analizado" (no es una salida
de la red).

Estrategia (memoria y CPU contenidas):
- Se trabaja sobre una miniatura (imagen completa) o la región de la anotación,
  igual que la detección de tejido / mapa de densidades, para no cargar la WSI
  entera en memoria. La miniatura sirve para el filtrado por tejido y para fijar
  la resolución del overlay.
- La región se cubre con una rejilla de celdas del tamaño físico del campo de
  entrenamiento. Cada celda con suficiente tejido (según la máscara clásica) se
  clasifica leyendo un campo REAL de la WSI en su centro.
- Se genera un overlay RGBA (mapa de clases) y un resumen de distribución por
  clase, cacheados en disco/BD.

Escala: el modelo se entrenó con las fotos de BACH (2048x1536 px a ~0.42 µm/px,
es decir, ~860x645 µm por imagen) reducidas a 299x299. Para respetar esa
distribución, cada celda lee un campo de ese tamaño físico (configurable con
``AI_FIELD_*``) que el clasificador reduce a 299x299. Solo se analizan celdas
con tejido; si superan ``AI_MAX_PATCHES`` se muestrean uniformemente entre
ellas y el resto se rellena (atenuado, solo en el overlay) con la clase del
campo evaluado más cercano. La cobertura se informa en el resultado.

Uso académico / de investigación: los porcentajes son de campos evaluados, no de
superficie, y la confianza softmax no está calibrada. No es un diagnóstico.
"""
from __future__ import annotations

import os
import math
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import AnalysisResult
from app.models.annotation import Annotation
from app.services.analysis.tissue_detection import DETECTOR_VERSION, detect_tissue
from app.services.analysis.annotation_analysis_service import (
    annotation_bbox,
    _shape_mask,
)
from app.services.analysis.inception_classifier import (  # noqa: F401
    MODEL_ID,
    MODEL_INPUT_SIZE,
    PREPROCESSING_VERSION,
    ModelUnavailableError,  # reexportado para los routers
    get_classifier,
)
from app.services.wsi.openslide_service import OpenSlideService

logger = logging.getLogger(__name__)

AI_ANALYSIS_TYPE = "ai_classification"
_THUMBNAIL_MAX_SIZE = 2048

# MPP por defecto si la WSI no expone metadatos de magnificación.
DEFAULT_MPP = 0.5

# Códigos de clase en el orden EXACTO de las salidas del modelo
# (benign, insitu, invasive, normal).
CLASS_CODES: List[str] = ["BENIGN", "INSITU", "INVASIVE", "NORMAL"]

# Metadatos por clase: nombre en español, grupo (uno por clase) y color RGB.
CLASS_META: Dict[str, Dict[str, Any]] = {
    "BENIGN": {"name": "Benigno", "group": "Benigno", "color": [59, 130, 246]},
    "INSITU": {
        "name": "Carcinoma in situ",
        "group": "Carcinoma in situ",
        "color": [245, 158, 11],
    },
    "INVASIVE": {
        "name": "Carcinoma invasivo",
        "group": "Carcinoma invasivo",
        "color": [220, 38, 38],
    },
    "NORMAL": {"name": "Normal", "group": "Normal", "color": [34, 197, 94]},
}

# Etiqueta de visualización para celdas no analizadas (no es salida del modelo).
BACKGROUND = {"code": "BACK", "name": "Fondo / no analizado", "color": [148, 163, 184]}

# Orden de presentación (de menor a mayor gravedad histológica).
GROUP_ORDER: List[str] = ["Normal", "Benigno", "Carcinoma in situ", "Carcinoma invasivo"]

# Color por grupo: el overlay, la leyenda y las barras usan siempre estos colores.
GROUP_COLORS: Dict[str, List[int]] = {
    meta["group"]: meta["color"] for meta in CLASS_META.values()
}

DISCLAIMER = (
    "Uso académico / de investigación. Clasificación por campos muestreados; "
    "la confianza no está calibrada y no constituye un diagnóstico clínico."
)


# --- Modelo ------------------------------------------------------------------

def _predict(patches: Sequence[np.ndarray]) -> Tuple[List[int], List[float], np.ndarray]:
    """Clasifica una lista de parches RGB. Devuelve (índices, confianzas, probs)."""
    probs = get_classifier().predict_batch(patches, batch_size=settings.AI_BATCH_SIZE)
    probs = np.asarray(probs, dtype=np.float32)
    if probs.ndim != 2 or probs.shape[1] != len(CLASS_CODES):
        raise ValueError(
            f"Salida del modelo inesperada {probs.shape}; se esperaban "
            f"{len(CLASS_CODES)} clases"
        )
    idx = probs.argmax(axis=1)
    conf = probs[np.arange(len(idx)), idx]
    return idx.tolist(), conf.tolist(), probs


def class_legend() -> List[Dict[str, Any]]:
    """Leyenda (código, nombre, grupo, color) de las clases del modelo."""
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


def _finish(
    labels: np.ndarray,
    confid: np.ndarray,
    prob_sum: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    width: int,
    height: int,
    inferred: Optional[np.ndarray] = None,
    clip: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Compone recuentos, confianza, probabilidades medias y overlay."""
    rows, cols = labels.shape
    analyzed = labels >= 0
    n = int(analyzed.sum())
    counts = {code: 0 for code in CLASS_CODES}
    for cls_idx in labels[analyzed].tolist():
        counts[CLASS_CODES[cls_idx]] += 1
    mean_probs = (prob_sum / n) if n else np.zeros(len(CLASS_CODES))

    return {
        "labels": labels.tolist(),
        "rows": rows,
        "cols": cols,
        "counts": counts,
        "tissue_patches": n,
        "total_patches": rows * cols,
        "mean_confidence": float(confid[analyzed].mean()) if n else 0.0,
        "mean_probabilities": {
            code: round(float(v), 4) for code, v in zip(CLASS_CODES, mean_probs)
        },
        "overlay": _labels_to_overlay(
            labels, x_edges, y_edges, width, height, inferred=inferred, clip=clip
        ),
    }


def _classify_into(
    patches: Sequence[np.ndarray],
    positions: Sequence[Tuple[int, int]],
    labels: np.ndarray,
    confid: np.ndarray,
    prob_sum: np.ndarray,
) -> None:
    """Clasifica ``patches`` y escribe el resultado en las celdas ``positions``."""
    if not patches:
        return
    preds, probs_max, probs = _predict(patches)
    for (r, c), cls_idx, conf in zip(positions, preds, probs_max):
        labels[r, c] = cls_idx
        confid[r, c] = conf
    prob_sum += probs.sum(axis=0)


def classify_rgb(
    rgb: np.ndarray,
    tissue_mask: Optional[np.ndarray] = None,
    *,
    max_patches: Optional[int] = None,
    min_tissue_frac: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Clasifica el tejido de una imagen RGB ya cargada en memoria, por celdas.

    Cada celda se entrega tal cual al clasificador (que la reduce a 299x299),
    sin control de escala física: útil para imágenes sueltas (p. ej. fotos tipo
    BACH) y pruebas. Para WSI se usa ``classify_slide_region``.
    """
    max_patches = max_patches or settings.AI_MAX_PATCHES
    if min_tissue_frac is None:
        min_tissue_frac = settings.AI_MIN_TISSUE_FRAC

    if rgb.ndim == 2:
        rgb = np.stack([rgb] * 3, axis=-1)
    if rgb.shape[-1] == 4:
        rgb = rgb[..., :3]
    rgb = np.ascontiguousarray(rgb.astype(np.uint8))

    height, width = rgb.shape[0], rgb.shape[1]
    cols, rows = _grid_shape(width, height, max_patches)
    x_edges = np.linspace(0, width, cols + 1).round().astype(int)
    y_edges = np.linspace(0, height, rows + 1).round().astype(int)

    patches: List[np.ndarray] = []
    positions: List[Tuple[int, int]] = []
    for r in range(rows):
        y0, y1 = y_edges[r], max(y_edges[r] + 1, y_edges[r + 1])
        for c in range(cols):
            x0, x1 = x_edges[c], max(x_edges[c] + 1, x_edges[c + 1])
            if tissue_mask is not None:
                frac = float(tissue_mask[y0:y1, x0:x1].mean())
                if frac < min_tissue_frac:
                    continue  # celda de fondo: se deja como -1
            patches.append(rgb[y0:y1, x0:x1])
            positions.append((r, c))

    labels = np.full((rows, cols), -1, dtype=np.int64)
    confid = np.zeros((rows, cols), dtype=np.float32)
    prob_sum = np.zeros(len(CLASS_CODES), dtype=np.float64)
    _classify_into(patches, positions, labels, confid, prob_sum)
    return _finish(labels, confid, prob_sum, x_edges, y_edges, width, height)


def field_size_level0(mpp: float) -> Tuple[int, int]:
    """Tamaño (ancho, alto) en px de nivel 0 del campo físico de entrenamiento."""
    factor = settings.AI_FIELD_MPP / mpp
    return (
        max(1, int(round(settings.AI_FIELD_WIDTH_PX * factor))),
        max(1, int(round(settings.AI_FIELD_HEIGHT_PX * factor))),
    )


def _spread_sample(n: int, k: int) -> np.ndarray:
    """``k`` índices de ``range(n)`` repartidos uniformemente (deterministas)."""
    if k >= n:
        return np.arange(n)
    return np.unique(np.linspace(0, n - 1, k).round().astype(int))


def _nearest_fill(labels: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Clase de la celda analizada más cercana para cada celda de ``targets``
    (-1 en el resto)."""
    from scipy.ndimage import distance_transform_edt

    known = labels >= 0
    if not known.any() or not targets.any():
        return np.full(labels.shape, -1, dtype=np.int64)
    _, (ri, ci) = distance_transform_edt(~known, return_indices=True)
    return np.where(targets, labels[ri, ci], -1)


def classify_slide_region(
    slide: "OpenSlideService",
    region_bbox: Tuple[int, int, int, int],
    thumb_rgb: np.ndarray,
    tissue_mask: Optional[np.ndarray],
    *,
    max_patches: Optional[int] = None,
    min_tissue_frac: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Clasifica una región de la WSI leyendo campos REALES a la escala física de
    entrenamiento (~860x645 µm por defecto), en lugar de aplastar una miniatura.

    La región se cubre con una rejilla densa (una celda = un campo). Solo se
    clasifican las celdas con tejido; si hay más que ``max_patches`` se elige un
    subconjunto repartido uniformemente entre ELLAS (el presupuesto nunca se
    gasta en fondo) y las celdas de tejido no evaluadas se rellenan, solo en el
    overlay y atenuadas, con la clase del campo evaluado más cercano. Los
    campos se leen en paralelo y se clasifican por bloques (memoria acotada).

    Args:
        slide: servicio OpenSlide abierto sobre la WSI.
        region_bbox: (x0, y0, w, h) de la región a clasificar, en px de nivel 0
            (imagen completa: (0, 0, W, H); anotación: su bounding box).
        thumb_rgb: miniatura de la región (para el filtrado por tejido y para
            fijar la resolución del overlay, alineado con la imagen base).
        tissue_mask: máscara booleana de tejido en la resolución de ``thumb_rgb``.
        max_patches: cota superior de campos clasificados.
        min_tissue_frac: fracción mínima de tejido de una celda para clasificarla.

    Devuelve el mismo formato que ``classify_rgb`` más metadatos de escala y
    cobertura.
    """
    from concurrent.futures import ThreadPoolExecutor

    max_patches = max_patches or settings.AI_MAX_PATCHES
    if min_tissue_frac is None:
        min_tissue_frac = settings.AI_MIN_TISSUE_FRAC

    x0, y0, region_w, region_h = region_bbox
    region_w, region_h = max(1, int(region_w)), max(1, int(region_h))
    thumb_h, thumb_w = thumb_rgb.shape[0], thumb_rgb.shape[1]

    slide_mpp = slide.get_mpp_x()
    mpp = slide_mpp or DEFAULT_MPP
    field_w, field_h = field_size_level0(mpp)
    out_h = MODEL_INPUT_SIZE
    out_w = max(1, int(round(MODEL_INPUT_SIZE * field_w / field_h)))

    # Rejilla densa: celdas del tamaño exacto del campo (la última, parcial).
    cols = max(1, int(math.ceil(region_w / field_w)))
    rows = max(1, int(math.ceil(region_h / field_h)))
    x_edges0 = np.minimum(np.arange(cols + 1) * field_w, region_w)
    y_edges0 = np.minimum(np.arange(rows + 1) * field_h, region_h)
    tx_edges = (x_edges0 * thumb_w / region_w).round().astype(int)
    ty_edges = (y_edges0 * thumb_h / region_h).round().astype(int)

    # Celdas con tejido suficiente (se analizan) y celdas de borde con algo de
    # tejido (no se analizan: se colorean con la clase del campo más cercano).
    tissue_grid = np.zeros((rows, cols), dtype=bool)
    edge_grid = np.zeros((rows, cols), dtype=bool)
    centers: Dict[Tuple[int, int], Tuple[float, float]] = {}
    sx, sy = region_w / thumb_w, region_h / thumb_h
    for r in range(rows):
        ty0, ty1 = ty_edges[r], max(ty_edges[r] + 1, ty_edges[r + 1])
        for c in range(cols):
            tx0, tx1 = tx_edges[c], max(tx_edges[c] + 1, tx_edges[c + 1])
            if tissue_mask is None:
                tissue_grid[r, c] = True
                continue
            cell = tissue_mask[ty0:ty1, tx0:tx1]
            frac = float(cell.mean()) if cell.size else 0.0
            if frac >= min_tissue_frac:
                tissue_grid[r, c] = True
                # El campo se centra en el tejido de la celda (no en su centro
                # geométrico), para que en los bordes vea tejido y no cristal.
                yy, xx = np.nonzero(cell)
                centers[(r, c)] = (
                    x0 + (tx0 + xx.mean() + 0.5) * sx,
                    y0 + (ty0 + yy.mean() + 0.5) * sy,
                )
            elif frac > 0:
                edge_grid[r, c] = True

    tissue_cells = [tuple(rc) for rc in np.argwhere(tissue_grid).tolist()]
    selected = [tissue_cells[i] for i in _spread_sample(len(tissue_cells), max_patches)]

    def _read(cell: Tuple[int, int]) -> np.ndarray:
        r, c = cell
        if cell in centers:
            cx, cy = centers[cell]
        else:
            cx = x0 + (int(x_edges0[c]) + int(x_edges0[c + 1])) / 2.0
            cy = y0 + (int(y_edges0[r]) + int(y_edges0[r + 1])) / 2.0
        return slide.read_field_rgb(cx, cy, field_w, field_h, out_w, out_h)

    labels = np.full((rows, cols), -1, dtype=np.int64)
    confid = np.zeros((rows, cols), dtype=np.float32)
    prob_sum = np.zeros(len(CLASS_CODES), dtype=np.float64)
    chunk = max(1, settings.AI_BATCH_SIZE * 4)
    with ThreadPoolExecutor(max_workers=max(1, settings.AI_READ_WORKERS)) as pool:
        for i in range(0, len(selected), chunk):
            cells = selected[i : i + chunk]
            patches = list(pool.map(_read, cells))
            _classify_into(patches, cells, labels, confid, prob_sum)

    inferred = _nearest_fill(labels, (tissue_grid & (labels < 0)) | edge_grid)
    result = _finish(
        labels, confid, prob_sum, tx_edges, ty_edges, thumb_w, thumb_h,
        inferred=inferred, clip=tissue_mask,
    )
    n_tissue = len(tissue_cells)
    result.update(
        {
            "mpp": round(float(mpp), 4),
            "mpp_source": "metadata" if slide_mpp else "default",
            "patch_px_level0": [field_w, field_h],
            "field_um": [round(field_w * mpp, 1), round(field_h * mpp, 1)],
            "tissue_cells": n_tissue,
            "inferred_cells": int((inferred >= 0).sum()),
            "coverage": round(len(selected) / n_tissue, 4) if n_tissue else 1.0,
            "sampled": len(selected) < n_tissue,
            "field_exceeds_region": field_w > region_w or field_h > region_h,
        }
    )
    return result


def _labels_to_overlay(
    labels: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    width: int,
    height: int,
    alpha: int = 140,
    inferred: Optional[np.ndarray] = None,
    inferred_alpha: int = 80,
    clip: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Colorea cada celda clasificada según su clase en una imagen RGBA (H, W, 4).

    Las celdas no analizadas (fondo) quedan transparentes. Las de ``inferred``
    (clase rellenada por vecindad; -1 si no aplica) se pintan atenuadas
    (``inferred_alpha``) para distinguirlas de las evaluadas por el modelo.
    Con ``clip`` (máscara de tejido del mismo tamaño) el color se limita al
    tejido: sigue su contorno y no se pinta sobre el cristal.
    """
    overlay = np.zeros((height, width, 4), dtype=np.uint8)
    rows, cols = labels.shape
    for r in range(rows):
        y0, y1 = y_edges[r], y_edges[r + 1]
        for c in range(cols):
            cls_idx, a = labels[r, c], alpha
            if cls_idx < 0 and inferred is not None and inferred[r, c] >= 0:
                cls_idx, a = inferred[r, c], inferred_alpha
            if cls_idx < 0:
                continue
            x0, x1 = x_edges[c], x_edges[c + 1]
            color = GROUP_COLORS[CLASS_META[CLASS_CODES[cls_idx]]["group"]]
            overlay[y0:y1, x0:x1, 0] = color[0]
            overlay[y0:y1, x0:x1, 1] = color[1]
            overlay[y0:y1, x0:x1, 2] = color[2]
            overlay[y0:y1, x0:x1, 3] = a
    if clip is not None and clip.shape == (height, width):
        overlay[~clip] = 0
    return overlay


# --- Resumen (distribución por clase y grupo) --------------------------------

def _build_summary(counts: Dict[str, int]) -> Dict[str, Any]:
    """Compone la distribución por clase y por grupo de los campos analizados."""
    tissue_total = sum(counts.get(code, 0) for code in CLASS_CODES)

    classes: List[Dict[str, Any]] = []
    for code in CLASS_CODES:
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
        group_counts[CLASS_META[code]["group"]] += counts.get(code, 0)

    groups: List[Dict[str, Any]] = []
    for g in GROUP_ORDER:
        count = group_counts.get(g, 0)
        percent = round(100.0 * count / tissue_total, 2) if tissue_total else 0.0
        groups.append(
            {"group": g, "color": GROUP_COLORS[g], "count": count, "percent": percent}
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
    return get_classifier().info()


def _is_current_model(analysis: AnalysisResult) -> bool:
    """True si el resultado cacheado se generó con el modelo, el preprocesado y el
    detector de tejido actuales."""
    model = (analysis.result_data or {}).get("model") or {}
    return (
        model.get("id") == MODEL_ID
        and model.get("preprocessing_version") == PREPROCESSING_VERSION
        and (analysis.result_data or {}).get("tissue_detector_version") == DETECTOR_VERSION
    )


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
    """Clasifica la región (campos reales a escala de entrenamiento), guarda el
    overlay PNG y persiste el AnalysisResult."""
    model_info = _model_info()  # carga el modelo: falla pronto si no hay pesos
    tissue = detect_tissue(thumb_rgb)
    result = classify_slide_region(slide, region_bbox, thumb_rgb, tissue.mask)

    PILImage.fromarray(result["overlay"], mode="RGBA").save(png_path, format="PNG")

    summary = _build_summary(result["counts"])
    data: Dict[str, Any] = {
        "type": AI_ANALYSIS_TYPE,
        "model": model_info,
        "map_path": png_path,
        "rows": result["rows"],
        "cols": result["cols"],
        "grid": result["labels"],
        "total_patches": result["total_patches"],
        "tissue_percent": round(tissue.tissue_percent, 4),
        "tissue_detector_version": DETECTOR_VERSION,
        "mean_confidence": round(result["mean_confidence"], 4),
        "mean_probabilities": result["mean_probabilities"],
        "mpp": result.get("mpp"),
        "sampling": {
            "mpp_source": result.get("mpp_source"),
            "field_px_level0": result.get("patch_px_level0"),
            "field_um": result.get("field_um"),
            "tissue_cells": result.get("tissue_cells"),
            "analyzed_cells": result["tissue_patches"],
            "inferred_cells": result.get("inferred_cells"),
            "coverage": result.get("coverage"),
            "sampled": result.get("sampled"),
            "field_exceeds_region": result.get("field_exceeds_region"),
            "max_patches": settings.AI_MAX_PATCHES,
            "min_tissue_frac": settings.AI_MIN_TISSUE_FRAC,
        },
        "legend": class_legend(),
        "background": BACKGROUND,
        "disclaimer": DISCLAIMER,
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


def _usable_cache(analysis: Optional[AnalysisResult]) -> bool:
    """El resultado cacheado existe, es del modelo actual y su PNG sigue en disco."""
    if analysis is None or not _is_current_model(analysis):
        return False
    map_path = (analysis.result_data or {}).get("map_path")
    return bool(map_path and os.path.exists(map_path))


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
        if _usable_cache(cached):
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
        # la forma para que el filtrado por tejido no clasifique fuera de la región.
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
        if _usable_cache(cached):
            return cached
    return generate_annotation_classification(db, annotation, file_path)
