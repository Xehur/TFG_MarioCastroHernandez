"""
Servicio de alto nivel para la detección de tejido de una imagen WSI.

Orquesta: lectura de miniatura (OpenSlide) -> detección (algoritmo) ->
cacheado del PNG de la máscara en disco y de las métricas en BD
(AnalysisResult con analysis_type="tissue_mask").
"""
import io
import os
import logging
from typing import Optional, Tuple

import numpy as np
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import AnalysisResult
from app.services.wsi.openslide_service import OpenSlideService
from app.services.analysis.tissue_detection import (
    detect_tissue,
    mask_to_rgba_overlay,
)

logger = logging.getLogger(__name__)

TISSUE_ANALYSIS_TYPE = "tissue_mask"
_THUMBNAIL_MAX_SIZE = 2048


def _analysis_dir(image_id: int) -> str:
    path = os.path.join(settings.UPLOAD_DIR, "analysis", str(image_id))
    os.makedirs(path, exist_ok=True)
    return path


def _mask_png_path(image_id: int) -> str:
    return os.path.join(_analysis_dir(image_id), "tissue_mask.png")


def get_cached_result(db: Session, image_id: int) -> Optional[AnalysisResult]:
    """Devuelve el AnalysisResult de tejido más reciente si existe."""
    return (
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.image_id == image_id,
            AnalysisResult.analysis_type == TISSUE_ANALYSIS_TYPE,
        )
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )


def generate_tissue_mask(
    db: Session,
    image_id: int,
    file_path: str,
    max_size: int = _THUMBNAIL_MAX_SIZE,
) -> AnalysisResult:
    """
    Ejecuta la detección de tejido, guarda el PNG de overlay en disco y
    persiste (o actualiza) el AnalysisResult con las métricas.
    """
    slide = OpenSlideService(file_path)
    try:
        rgb, scale = slide.get_thumbnail_rgb(max_size=max_size)
    finally:
        slide.close()

    result = detect_tissue(rgb)

    overlay = mask_to_rgba_overlay(result.mask)
    png_path = _mask_png_path(image_id)
    PILImage.fromarray(overlay, mode="RGBA").save(png_path, format="PNG")

    stats = result.stats()
    stats["scale"] = scale
    stats["mask_path"] = png_path
    stats["thumbnail_max_size"] = max_size

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
            mask_path = (cached.result_data or {}).get("mask_path")
            if mask_path and os.path.exists(mask_path):
                return cached
    return generate_tissue_mask(db, image_id, file_path)


def load_mask_png_bytes(analysis: AnalysisResult) -> bytes:
    """Lee los bytes del PNG de la máscara desde disco."""
    mask_path = (analysis.result_data or {}).get("mask_path")
    if not mask_path or not os.path.exists(mask_path):
        raise FileNotFoundError("PNG de máscara no encontrado")
    with open(mask_path, "rb") as fh:
        return fh.read()
