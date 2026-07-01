"""
Router para análisis de imagen (Sprint 6).

Endpoints:
- GET /images/{image_id}/tissue-mask         PNG de la máscara de tejido (overlay)
- GET /images/{image_id}/tissue-mask/stats   estadísticas del análisis (JSON)
- POST /images/{image_id}/analyze/tissue     fuerza el (re)análisis de tejido
"""
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.image import Image
from app.schemas.analysis import AnalysisResultResponse
from app.services.analysis import tissue_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


def _get_image_or_404(db: Session, image_id: int) -> Image:
    image = db.query(Image).filter(Image.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    return image


def _ensure_file_exists(image: Image) -> None:
    if not image.file_path or not os.path.exists(image.file_path):
        raise HTTPException(
            status_code=404, detail="Archivo de imagen no encontrado"
        )


@router.get("/images/{image_id}/tissue-mask")
def get_tissue_mask(
    image_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve el PNG (RGBA) de la máscara de tejido. Lo genera si no existe."""
    image = _get_image_or_404(db, image_id)
    _ensure_file_exists(image)

    try:
        analysis = tissue_service.get_or_create_tissue_mask(
            db, image_id, image.file_path, force=force
        )
        png_bytes = tissue_service.load_mask_png_bytes(analysis)
    except FileNotFoundError:
        # El registro existía pero el PNG no; regenerar.
        analysis = tissue_service.generate_tissue_mask(
            db, image_id, image.file_path
        )
        png_bytes = tissue_service.load_mask_png_bytes(analysis)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error generando máscara de tejido: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error generando máscara de tejido: {exc}"
        )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/images/{image_id}/tissue-mask/stats",
    response_model=AnalysisResultResponse,
)
def get_tissue_mask_stats(
    image_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve las estadísticas del análisis de tejido (JSON)."""
    image = _get_image_or_404(db, image_id)
    _ensure_file_exists(image)

    try:
        analysis = tissue_service.get_or_create_tissue_mask(
            db, image_id, image.file_path, force=force
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en análisis de tejido: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en análisis de tejido: {exc}"
        )
    return analysis


@router.post(
    "/images/{image_id}/analyze/tissue",
    response_model=AnalysisResultResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_tissue(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fuerza el (re)análisis de tejido y devuelve las estadísticas."""
    image = _get_image_or_404(db, image_id)
    _ensure_file_exists(image)

    try:
        analysis = tissue_service.generate_tissue_mask(
            db, image_id, image.file_path
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en análisis de tejido: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en análisis de tejido: {exc}"
        )
    return analysis
