"""
Servicio de alto nivel para la detección de tejido de una imagen WSI.

Orquesta: lectura de miniatura (OpenSlide) -> detección (algoritmo) ->
cacheado del PNG de la máscara en disco y de las métricas en BD
(AnalysisResult con analysis_type="tissue_mask").
"""
import io
import os
import logging
import threading
from collections import OrderedDict
from typing import Optional, Tuple

import numpy as np
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import AnalysisResult
from app.services.wsi.openslide_service import OpenSlideService
from app.services.analysis.tissue_detection import (
    DEFAULT_THRESHOLD_FACTOR,
    clamp_threshold_factor,
    detect_tissue,
    is_current_detector,
    mask_to_rgba_overlay,
)

logger = logging.getLogger(__name__)

TISSUE_ANALYSIS_TYPE = "tissue_mask"
_THUMBNAIL_MAX_SIZE = 2048
# La vista previa del umbral usa una miniatura menor para responder en ~0,2 s.
PREVIEW_MAX_SIZE = 1024
_PREVIEW_CACHE_SIZE = 4

_preview_thumbs: "OrderedDict[Tuple[str, float, int], Tuple[np.ndarray, float]]" = OrderedDict()
_preview_lock = threading.Lock()


def _analysis_dir(image_id: int) -> str:
    path = os.path.join(settings.UPLOAD_DIR, "analysis", str(image_id))
    os.makedirs(path, exist_ok=True)
    return path


def load_thumbnail_rgb(file_path: str, max_size: int = _THUMBNAIL_MAX_SIZE):
    """Lee la miniatura RGB de una imagen (abre y cierra el slide)."""
    slide = OpenSlideService(file_path)
    try:
        return slide.get_thumbnail_rgb(max_size=max_size)
    finally:
        slide.close()


def _mask_png_path(image_id: int) -> str:
    return os.path.join(_analysis_dir(image_id), "tissue_mask.png")


def get_cached_result(db: Session, image_id: int) -> Optional[AnalysisResult]:
    """Devuelve el AnalysisResult de tejido más reciente si existe."""
    return (
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.image_id == image_id,
            AnalysisResult.annotation_id.is_(None),
            AnalysisResult.analysis_type == TISSUE_ANALYSIS_TYPE,
        )
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )


def get_threshold_factor(db: Session, image_id: int) -> float:
    """Factor de umbral de tejido elegido por el usuario para una imagen (1.0
    si no lo ha cambiado). Se guarda con la máscara de tejido de la imagen y lo
    usan también la densidad y la clasificación IA, para que todos los análisis
    trabajen sobre el mismo tejido."""
    cached = get_cached_result(db, image_id)
    data = (cached.result_data or {}) if cached is not None else {}
    return clamp_threshold_factor(data.get("threshold_factor", DEFAULT_THRESHOLD_FACTOR))


def _preview_thumbnail(file_path: str, max_size: int) -> Tuple[np.ndarray, float]:
    """Miniatura para la vista previa, cacheada en memoria (pocas entradas)
    para que mover el deslizador no relea la WSI en cada petición."""
    try:
        mtime = os.path.getmtime(file_path)
    except OSError:
        mtime = 0.0
    key = (os.path.abspath(file_path), mtime, max_size)
    with _preview_lock:
        if key in _preview_thumbs:
            _preview_thumbs.move_to_end(key)
            return _preview_thumbs[key]
    value = load_thumbnail_rgb(file_path, max_size=max_size)
    with _preview_lock:
        _preview_thumbs[key] = value
        while len(_preview_thumbs) > _PREVIEW_CACHE_SIZE:
            _preview_thumbs.popitem(last=False)
    return value


def preview_tissue_mask(
    file_path: str, threshold_factor: float, max_size: int = PREVIEW_MAX_SIZE
) -> Tuple[bytes, dict]:
    """Calcula la máscara con un factor de umbral SIN guardarla (vista previa
    del deslizador). Devuelve el PNG del overlay y sus métricas."""
    rgb, scale = _preview_thumbnail(file_path, max_size)
    result = detect_tissue(rgb, threshold_factor=threshold_factor)
    buffer = io.BytesIO()
    PILImage.fromarray(mask_to_rgba_overlay(result.mask), mode="RGBA").save(
        buffer, format="PNG"
    )
    return buffer.getvalue(), {**result.stats(), "scale": scale, "preview": True}


def generate_tissue_mask(
    db: Session,
    image_id: int,
    file_path: str,
    max_size: int = _THUMBNAIL_MAX_SIZE,
    *,
    rgb=None,
    scale: Optional[float] = None,
    tissue=None,
    threshold_factor: Optional[float] = None,
) -> AnalysisResult:
    """
    Ejecuta la detección de tejido, guarda el PNG de overlay en disco y
    persiste (o actualiza) el AnalysisResult con las métricas.

    ``rgb``/``scale``/``tissue`` opcionales permiten reutilizar una miniatura y
    una detección ya calculadas (p.ej. en el análisis consolidado), evitando
    releer la imagen y recomputar la detección. ``threshold_factor`` fija el
    factor de umbral; si se omite se conserva el que ya tenía la imagen.
    """
    if threshold_factor is None:
        threshold_factor = get_threshold_factor(db, image_id)
    threshold_factor = clamp_threshold_factor(threshold_factor)

    if rgb is None or scale is None:
        slide = OpenSlideService(file_path)
        try:
            rgb, scale = slide.get_thumbnail_rgb(max_size=max_size)
        finally:
            slide.close()

    result = (
        tissue if tissue is not None
        else detect_tissue(rgb, threshold_factor=threshold_factor)
    )

    overlay = mask_to_rgba_overlay(result.mask)
    png_path = _mask_png_path(image_id)
    PILImage.fromarray(overlay, mode="RGBA").save(png_path, format="PNG")

    stats = result.stats()
    stats["scale"] = scale
    stats["mask_path"] = png_path
    stats["thumbnail_max_size"] = max_size
    stats["detector_mode"] = "classical"

    existing = get_cached_result(db, image_id)
    if existing is not None:
        existing.result_data = stats
        db.commit()
        db.refresh(existing)
        return existing

    analysis = AnalysisResult(
        image_id=image_id,
        analysis_type=TISSUE_ANALYSIS_TYPE,
        result_data=stats,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def get_or_create_tissue_mask(
    db: Session,
    image_id: int,
    file_path: str,
    force: bool = False,
) -> AnalysisResult:
    """
    Devuelve el resultado cacheado si existe (y el PNG está en disco), o lo
    genera. Con ``force=True`` siempre regenera.
    """
    if not force:
        cached = get_cached_result(db, image_id)
        if cached is not None:
            data = cached.result_data or {}
            mask_path = data.get("mask_path")
            # Regenera máscaras generadas por el antiguo detector de IA
            # (detector_mode != "classical" o ausente) para auto-curarlas.
            factor = clamp_threshold_factor(
                data.get("threshold_factor", DEFAULT_THRESHOLD_FACTOR)
            )
            mode_ok = data.get("detector_mode") == "classical" and is_current_detector(
                data, factor
            )
            if mask_path and os.path.exists(mask_path) and mode_ok:
                return cached
    return generate_tissue_mask(db, image_id, file_path)


def load_mask_png_bytes(analysis: AnalysisResult) -> bytes:
    """Lee los bytes del PNG de la máscara desde disco."""
    mask_path = (analysis.result_data or {}).get("mask_path")
    if not mask_path or not os.path.exists(mask_path):
        raise FileNotFoundError("PNG de máscara no encontrado")
    with open(mask_path, "rb") as fh:
        return fh.read()
