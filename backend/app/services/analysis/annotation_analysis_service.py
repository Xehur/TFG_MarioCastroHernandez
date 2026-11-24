"""
Servicio de análisis de zonas anotadas (regiones marcadas por el usuario).

Permite ejecutar los mismos análisis que sobre una imagen completa (detección
de tejido, mapa de densidades, análisis consolidado y analíticas) pero acotados
a la región de una anotación (rectángulo, círculo o polígono), tratándola "como
si fuese una WSI aparte".

Estrategia (memoria contenida):
- Se lee únicamente el rectángulo delimitador (bounding box) de la anotación
  mediante ``OpenSlideService.read_region_rgb``, eligiendo el nivel de la
  pirámide que mantiene la región por debajo de ~2048 px.
- Para formas no rectangulares (círculo, polígono) se enmascaran a blanco los
  píxeles fuera de la forma, de modo que la detección de tejido los ignore.
- Se reutilizan ``detect_tissue`` y ``generate_density_map``.
- Los resultados se cachean en BD indexados por ``annotation_id`` y los PNG en
  ``{UPLOAD_DIR}/analysis/{image_id}/ann_{annotation_id}/``.
"""
import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image as PILImage, ImageDraw
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import AnalysisResult, DensityMap
from app.models.annotation import Annotation
from app.services.wsi.openslide_service import OpenSlideService
from app.services.analysis.tissue_detection import (
    detect_tissue,
    DETECTOR_VERSION,
    is_current_detector,
    mask_to_rgba_overlay,
)
from app.services.analysis.density_generation import (
    generate_density_map,
    density_to_heatmap_rgba,
    _colormap_lut,
    DEFAULT_COLORMAP,
)
from app.services.analysis import analytics_service
from app.services.analysis import tissue_service

logger = logging.getLogger(__name__)

TISSUE_ANALYSIS_TYPE = "tissue_mask"
FULL_ANALYSIS_TYPE = "full_analysis"
DEFAULT_GRID_SIZE = 64
_REGION_MAX_SIZE = 2048


# --- Geometría de la anotación ----------------------------------------------

def annotation_bbox(shape_type: str, coords: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """Rectángulo delimitador (x, y, w, h) en píxeles base de la anotación."""
    if shape_type == "rectangle":
        x = float(coords["x"])
        y = float(coords["y"])
        w = float(coords["width"])
        h = float(coords["height"])
    elif shape_type == "circle":
        cx = float(coords["x"])
        cy = float(coords["y"])
        r = float(coords["radius"])
        x, y, w, h = cx - r, cy - r, 2 * r, 2 * r
    elif shape_type == "polygon":
        points = coords.get("points") or []
        if not points:
            raise ValueError("El polígono no tiene puntos")
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        x, y = min(xs), min(ys)
        w, h = max(xs) - x, max(ys) - y
    else:
        raise ValueError(f"Tipo de forma no soportado: {shape_type}")
    return int(round(x)), int(round(y)), int(round(w)), int(round(h))


def _shape_mask(
    shape_type: str,
    coords: Dict[str, Any],
    used_bbox: Tuple[int, int, int, int],
    out_w: int,
    out_h: int,
    scale: float,
) -> Optional[np.ndarray]:
    """
    Máscara booleana (out_h, out_w) de los píxeles que caen dentro de la forma,
    en la resolución de la región leída. Devuelve None para rectángulos (toda
    la región es válida).
    """
    if shape_type == "rectangle":
        return None

    x0, y0, _, _ = used_bbox
    mask_img = PILImage.new("L", (out_w, out_h), 0)
    draw = ImageDraw.Draw(mask_img)

    def to_region(px: float, py: float) -> Tuple[float, float]:
        return (px - x0) / scale, (py - y0) / scale

    if shape_type == "circle":
        cx, cy = to_region(float(coords["x"]), float(coords["y"]))
        r = float(coords["radius"]) / scale
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    elif shape_type == "polygon":
        points = [
            to_region(float(p[0]), float(p[1]))
            for p in (coords.get("points") or [])
        ]
        if len(points) >= 3:
            draw.polygon(points, fill=255)
    return np.asarray(mask_img) > 0


def _load_region_rgb(
    annotation: Annotation, file_path: str, max_size: int = _REGION_MAX_SIZE
) -> Tuple[np.ndarray, float, Tuple[int, int, int, int]]:
    """
    Lee la región de la anotación como RGB y, para formas no rectangulares,
    enmascara a blanco (fondo) los píxeles fuera de la forma.
    """
    bbox = annotation_bbox(annotation.shape_type, annotation.coordinates or {})
    slide = OpenSlideService(file_path)
    try:
        rgb, scale, used_bbox = slide.read_region_rgb(*bbox, max_size=max_size)
    finally:
        slide.close()

    mask = _shape_mask(
        annotation.shape_type,
        annotation.coordinates or {},
        used_bbox,
        rgb.shape[1],
        rgb.shape[0],
        scale,
    )
    if mask is not None:
        rgb = rgb.copy()
        rgb[~mask] = 255
    return rgb, scale, used_bbox


# --- Rutas de caché en disco -------------------------------------------------

def _analysis_dir(image_id: int, annotation_id: int) -> str:
    path = os.path.join(
        settings.UPLOAD_DIR, "analysis", str(image_id), f"ann_{annotation_id}"
    )
    os.makedirs(path, exist_ok=True)
    return path


def _mask_png_path(image_id: int, annotation_id: int) -> str:
    return os.path.join(_analysis_dir(image_id, annotation_id), "tissue_mask.png")


def _heatmap_png_path(
    image_id: int, annotation_id: int, grid_size: int, colormap: str
) -> str:
    return os.path.join(
        _analysis_dir(image_id, annotation_id),
        f"density_{grid_size}_{colormap}.png",
    )


# --- Tejido ------------------------------------------------------------------

def get_cached_tissue(db: Session, annotation_id: int) -> Optional[AnalysisResult]:
    return (
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.annotation_id == annotation_id,
            AnalysisResult.analysis_type == TISSUE_ANALYSIS_TYPE,
        )
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )


def generate_tissue_mask(
    db: Session,
    annotation: Annotation,
    file_path: str,
    *,
    rgb=None,
    scale: Optional[float] = None,
    used_bbox: Optional[Tuple[int, int, int, int]] = None,
    tissue=None,
) -> AnalysisResult:
    """Detecta tejido en la región de la anotación y cachea PNG + métricas."""
    if rgb is None or scale is None or used_bbox is None:
        rgb, scale, used_bbox = _load_region_rgb(annotation, file_path)

    factor = tissue_service.get_threshold_factor(db, annotation.image_id)
    result = (
        tissue if tissue is not None
        else detect_tissue(rgb, threshold_factor=factor)
    )

    overlay = mask_to_rgba_overlay(result.mask)
    png_path = _mask_png_path(annotation.image_id, annotation.id)
    PILImage.fromarray(overlay, mode="RGBA").save(png_path, format="PNG")

    stats = result.stats()
    stats["scale"] = scale
    stats["mask_path"] = png_path
    stats["annotation_id"] = annotation.id
    stats["bbox"] = list(used_bbox)

    existing = get_cached_tissue(db, annotation.id)
    if existing is not None:
        existing.result_data = stats
        db.commit()
        db.refresh(existing)
        return existing

    analysis = AnalysisResult(
        image_id=annotation.image_id,
        annotation_id=annotation.id,
        analysis_type=TISSUE_ANALYSIS_TYPE,
        result_data=stats,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def get_or_create_tissue_mask(
    db: Session, annotation: Annotation, file_path: str, force: bool = False
) -> AnalysisResult:
    if not force:
        cached = get_cached_tissue(db, annotation.id)
        if cached is not None:
            mask_path = (cached.result_data or {}).get("mask_path")
            if (
                mask_path
                and os.path.exists(mask_path)
                and is_current_detector(
                    cached.result_data,
                    tissue_service.get_threshold_factor(db, annotation.image_id),
                )
            ):
                return cached
    return generate_tissue_mask(db, annotation, file_path)


def load_mask_png_bytes(analysis: AnalysisResult) -> bytes:
    mask_path = (analysis.result_data or {}).get("mask_path")
    if not mask_path or not os.path.exists(mask_path):
        raise FileNotFoundError("PNG de máscara no encontrado")
    with open(mask_path, "rb") as fh:
        return fh.read()


# --- Densidad ----------------------------------------------------------------

def _exact_cached_density(
    db: Session, annotation_id: int, grid_size: int, colormap: str
) -> Optional[DensityMap]:
    candidates = (
        db.query(DensityMap)
        .filter(
            DensityMap.annotation_id == annotation_id,
            DensityMap.grid_size == grid_size,
        )
        .order_by(DensityMap.created_at.desc())
        .all()
    )
    for candidate in candidates:
        if (candidate.density_data or {}).get("colormap") == colormap:
            return candidate
    return None


def get_cached_density(db: Session, annotation_id: int) -> Optional[DensityMap]:
    return (
        db.query(DensityMap)
        .filter(DensityMap.annotation_id == annotation_id)
        .order_by(DensityMap.created_at.desc())
        .first()
    )


def generate_density(
    db: Session,
    annotation: Annotation,
    file_path: str,
    grid_size: int = DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    *,
    rgb=None,
    scale: Optional[float] = None,
    used_bbox: Optional[Tuple[int, int, int, int]] = None,
    tissue=None,
) -> DensityMap:
    """Genera el mapa de densidades de la región de la anotación."""
    if rgb is None or scale is None or used_bbox is None:
        rgb, scale, used_bbox = _load_region_rgb(annotation, file_path)

    factor = tissue_service.get_threshold_factor(db, annotation.image_id)
    tissue = (
        tissue if tissue is not None
        else detect_tissue(rgb, threshold_factor=factor)
    )
    _, _, region_w, region_h = used_bbox

    result = generate_density_map(
        tissue.mask,
        grid_size=grid_size,
        base_width=region_w,
        base_height=region_h,
        colormap=colormap,
    )

    heatmap = density_to_heatmap_rgba(
        result.density,
        out_shape=(tissue.height, tissue.width),
        colormap=colormap,
    )
    png_path = _heatmap_png_path(
        annotation.image_id, annotation.id, grid_size, colormap
    )
    PILImage.fromarray(heatmap, mode="RGBA").save(png_path, format="PNG")

    data = result.stats()
    data["scale"] = scale
    data["map_path"] = png_path
    data["annotation_id"] = annotation.id
    data["bbox"] = list(used_bbox)
    data["tissue_percent"] = round(tissue.tissue_percent, 4)
    data["detector_version"] = DETECTOR_VERSION
    data["threshold_factor"] = tissue.extra.get("threshold_factor", factor)
    data["colorbar"] = _colormap_lut(colormap, samples=16)

    existing = _exact_cached_density(db, annotation.id, grid_size, colormap)
    if existing is not None:
        existing.density_data = data
        db.commit()
        db.refresh(existing)
        return existing

    density_map = DensityMap(
        image_id=annotation.image_id,
        annotation_id=annotation.id,
        grid_size=grid_size,
        density_data=data,
    )
    db.add(density_map)
    db.commit()
    db.refresh(density_map)
    return density_map


def get_or_create_density(
    db: Session,
    annotation: Annotation,
    file_path: str,
    grid_size: int = DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    force: bool = False,
) -> DensityMap:
    if not force:
        cached = _exact_cached_density(db, annotation.id, grid_size, colormap)
        if cached is not None:
            map_path = (cached.density_data or {}).get("map_path")
            if (
                map_path
                and os.path.exists(map_path)
                and is_current_detector(
                    cached.density_data,
                    tissue_service.get_threshold_factor(db, annotation.image_id),
                )
            ):
                return cached
    return generate_density(db, annotation, file_path, grid_size, colormap)


def load_heatmap_png_bytes(density_map: DensityMap) -> bytes:
    map_path = (density_map.density_data or {}).get("map_path")
    if not map_path or not os.path.exists(map_path):
        raise FileNotFoundError("PNG de mapa de densidad no encontrado")
    with open(map_path, "rb") as fh:
        return fh.read()


# --- Análisis consolidado ----------------------------------------------------

def get_full_analysis(db: Session, annotation_id: int) -> Optional[AnalysisResult]:
    return (
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.annotation_id == annotation_id,
            AnalysisResult.analysis_type == FULL_ANALYSIS_TYPE,
        )
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )


def run_full_analysis(
    db: Session,
    annotation: Annotation,
    file_path: str,
    grid_size: int = DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
) -> AnalysisResult:
    """
    Ejecuta tejido + densidad sobre la región de la anotación reutilizando una
    sola lectura de la región y una sola detección de tejido.
    """
    rgb, scale, used_bbox = _load_region_rgb(annotation, file_path)
    tissue_detection = detect_tissue(
        rgb,
        threshold_factor=tissue_service.get_threshold_factor(db, annotation.image_id),
    )

    tissue = generate_tissue_mask(
        db, annotation, file_path,
        rgb=rgb, scale=scale, used_bbox=used_bbox, tissue=tissue_detection,
    )
    density = generate_density(
        db, annotation, file_path, grid_size=grid_size, colormap=colormap,
        rgb=rgb, scale=scale, used_bbox=used_bbox, tissue=tissue_detection,
    )

    tissue_data = tissue.result_data or {}
    density_data = density.density_data or {}
    summary = {
        "annotation_id": annotation.id,
        "shape_type": annotation.shape_type,
        "bbox": list(used_bbox),
        "tissue": {
            "tissue_percent": tissue_data.get("tissue_percent"),
            "width": tissue_data.get("width"),
            "height": tissue_data.get("height"),
            "method": tissue_data.get("method"),
        },
        "density": {
            "grid_size": grid_size,
            "colormap": colormap,
            "density_min": density_data.get("density_min"),
            "density_max": density_data.get("density_max"),
            "density_mean": density_data.get("density_mean"),
            "density_std": density_data.get("density_std"),
            "rows": density_data.get("rows"),
            "cols": density_data.get("cols"),
        },
        "grid_size": grid_size,
        "colormap": colormap,
        "analyzed_at": datetime.utcnow().isoformat(),
    }

    existing = get_full_analysis(db, annotation.id)
    if existing is not None:
        existing.result_data = summary
        db.commit()
        db.refresh(existing)
        return existing

    analysis = AnalysisResult(
        image_id=annotation.image_id,
        annotation_id=annotation.id,
        analysis_type=FULL_ANALYSIS_TYPE,
        result_data=summary,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


# --- Analíticas de la anotación ---------------------------------------------

def build_annotation_analytics(
    db: Session,
    annotation: Annotation,
    spatial_bins: int = analytics_service.DEFAULT_SPATIAL_BINS,
    histogram_bins: int = analytics_service.DEFAULT_HISTOGRAM_BINS,
) -> Dict[str, Any]:
    """
    Compone las analíticas de una región anotada, con la misma estructura que
    las de una imagen para reutilizar el dashboard. La región no tiene
    sub-anotaciones propias, así que los recuentos de anotaciones van vacíos y
    lo relevante son las estadísticas de tejido y la densidad por zonas.
    """
    from app.models.image import Image as ImageModel
    from app.services.analysis import ai_classification_service as ai

    tissue_result = get_cached_tissue(db, annotation.id)
    density_map = get_cached_density(db, annotation.id)
    image = db.query(ImageModel).filter(ImageModel.id == annotation.image_id).first()
    mpp = analytics_service.image_mpp(image.properties if image else None)
    _, _, region_w, region_h = annotation_bbox(
        annotation.shape_type, annotation.coordinates or {}
    )
    tissue = analytics_service._tissue_stats_from_result(tissue_result, mpp)
    region_mm2 = (
        round(
            analytics_service.annotation_area_px(
                annotation.shape_type, annotation.coordinates or {}
            )
            * (mpp / 1000.0) ** 2,
            3,
        )
        if mpp
        else None
    )

    empty_grid: List[List[int]] = [
        [0 for _ in range(spatial_bins)] for _ in range(spatial_bins)
    ]

    return {
        "image_id": annotation.image_id,
        "annotation_id": annotation.id,
        "total_annotations": 0,
        "annotated_area_mm2": region_mm2,
        "by_type": [],
        "by_class": [],
        "distribution": [],
        "spatial": {"bins": spatial_bins, "grid": empty_grid, "max": 0},
        "tissue": tissue,
        "density_zones": analytics_service._density_zones_from_map(
            density_map, histogram_bins
        ),
        "density_levels": analytics_service.density_levels(density_map),
        "image_info": analytics_service.image_info(int(region_w), int(region_h), mpp),
        "ai": analytics_service.ai_summary(
            ai.get_cached_annotation_classification(db, annotation.id),
            tissue["area_mm2"] if tissue else None,
        ),
    }
