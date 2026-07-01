"""
Router para análisis de imagen (Sprint 6).

Endpoints:
- GET /images/{image_id}/tissue-mask         PNG de la máscara de tejido (overlay)
- GET /images/{image_id}/tissue-mask/stats   estadísticas del análisis (JSON)
- POST /images/{image_id}/analyze/tissue     fuerza el (re)análisis de tejido
- GET /images/{image_id}/density-map         PNG del heatmap de densidad
- GET /images/{image_id}/density-map/stats   matriz de densidad + metadatos (JSON)
- POST /images/{image_id}/analyze/density    fuerza la (re)generación del mapa
- POST /images/{image_id}/analyze            análisis consolidado (tejido + densidad)
- GET /images/{image_id}/analysis            último análisis consolidado (JSON)
"""
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.image import Image
from app.schemas.analysis import (
    AnalysisResultResponse,
    DensityMapResponse,
    FullAnalysisResponse,
)
from app.services.analysis import tissue_service, density_service, analysis_service
from app.services.analysis.density_generation import (
    SUPPORTED_COLORMAPS,
    DEFAULT_COLORMAP,
)

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


# --- Mapa de densidades (issues 31, 33) --------------------------------------

_MIN_GRID_SIZE = 16
_MAX_GRID_SIZE = 8192


def _validate_density_params(grid_size: int, colormap: str) -> None:
    if grid_size < _MIN_GRID_SIZE or grid_size > _MAX_GRID_SIZE:
        raise HTTPException(
            status_code=422,
            detail=(
                f"grid_size debe estar entre {_MIN_GRID_SIZE} y {_MAX_GRID_SIZE}"
            ),
        )
    if colormap not in SUPPORTED_COLORMAPS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"colormap no soportado. Opciones: {', '.join(SUPPORTED_COLORMAPS)}"
            ),
        )


@router.get("/images/{image_id}/density-map")
def get_density_map(
    image_id: int,
    grid_size: int = density_service.DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve el PNG (RGBA) del heatmap de densidad. Lo genera si no existe."""
    _validate_density_params(grid_size, colormap)
    image = _get_image_or_404(db, image_id)
    _ensure_file_exists(image)

    try:
        density_map = density_service.get_or_create_density(
            db, image_id, image.file_path, grid_size, colormap, force=force
        )
        png_bytes = density_service.load_heatmap_png_bytes(density_map)
    except FileNotFoundError:
        density_map = density_service.generate_density(
            db, image_id, image.file_path, grid_size, colormap
        )
        png_bytes = density_service.load_heatmap_png_bytes(density_map)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error generando mapa de densidad: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generando mapa de densidad: {exc}",
        )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/images/{image_id}/density-map/stats",
    response_model=DensityMapResponse,
)
def get_density_map_stats(
    image_id: int,
    grid_size: int = density_service.DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve la matriz de densidades y sus metadatos (JSON)."""
    _validate_density_params(grid_size, colormap)
    image = _get_image_or_404(db, image_id)
    _ensure_file_exists(image)

    try:
        density_map = density_service.get_or_create_density(
            db, image_id, image.file_path, grid_size, colormap, force=force
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en mapa de densidad: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en mapa de densidad: {exc}"
        )
    return density_map


@router.post(
    "/images/{image_id}/analyze/density",
    response_model=DensityMapResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_density(
    image_id: int,
    grid_size: int = density_service.DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fuerza la (re)generación del mapa de densidades y devuelve los datos."""
    _validate_density_params(grid_size, colormap)
    image = _get_image_or_404(db, image_id)
    _ensure_file_exists(image)

    try:
        density_map = density_service.generate_density(
            db, image_id, image.file_path, grid_size, colormap
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en mapa de densidad: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en mapa de densidad: {exc}"
        )
    return density_map


# --- Análisis consolidado en tiempo real (issue 37) --------------------------

@router.post(
    "/images/{image_id}/analyze",
    response_model=FullAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_image(
    image_id: int,
    grid_size: int = density_service.DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ejecuta el análisis completo (tejido + densidad) y guarda el resumen."""
    _validate_density_params(grid_size, colormap)
    image = _get_image_or_404(db, image_id)
    _ensure_file_exists(image)

    try:
        analysis = analysis_service.run_full_analysis(
            db, image_id, image.file_path, grid_size, colormap
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en análisis consolidado: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en análisis consolidado: {exc}"
        )
    return analysis


@router.get(
    "/images/{image_id}/analysis",
    response_model=FullAnalysisResponse,
)
def get_analysis(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve el último análisis consolidado de la imagen (404 si no existe)."""
    _get_image_or_404(db, image_id)
    analysis = analysis_service.get_full_analysis(db, image_id)
    if analysis is None:
        raise HTTPException(
            status_code=404, detail="La imagen no tiene análisis todavía"
        )
    return analysis
