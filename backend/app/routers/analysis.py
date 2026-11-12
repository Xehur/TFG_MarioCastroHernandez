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
- GET /images/{image_id}/analytics           datos para gráficas y tablas (JSON)
"""
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.image import Image
from app.models.annotation import Annotation
from app.schemas.analysis import (
    AnalysisResultResponse,
    DensityMapResponse,
    FullAnalysisResponse,
    AnalyticsResponse,
)
from app.services.analysis import (
    tissue_service,
    density_service,
    analysis_service,
    analytics_service,
    annotation_analysis_service,
    ai_classification_service,
)
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


def _get_annotation_ctx(db: Session, annotation_id: int):
    """Devuelve (annotation, image) validando existencia y archivo."""
    annotation = (
        db.query(Annotation).filter(Annotation.id == annotation_id).first()
    )
    if annotation is None:
        raise HTTPException(status_code=404, detail="Anotación no encontrada")
    image = _get_image_or_404(db, annotation.image_id)
    _ensure_file_exists(image)
    return annotation, image


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
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
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
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
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


# --- Analíticas (issue 46) ---------------------------------------------------

@router.get(
    "/images/{image_id}/analytics",
    response_model=AnalyticsResponse,
)
def get_analytics(
    image_id: int,
    spatial_bins: int = analytics_service.DEFAULT_SPATIAL_BINS,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve datos de analíticas (distribución, espacial, tejido, densidad)."""
    if spatial_bins < 2 or spatial_bins > 100:
        raise HTTPException(
            status_code=422, detail="spatial_bins debe estar entre 2 y 100"
        )
    image = _get_image_or_404(db, image_id)
    try:
        return analytics_service.build_analytics(
            db,
            image_id,
            width=image.width or 0,
            height=image.height or 0,
            spatial_bins=spatial_bins,
            mpp=analytics_service.image_mpp(image.properties),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error generando analíticas: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error generando analíticas: {exc}"
        )


# --- Análisis de zonas anotadas (anotaciones como WSI aparte) ----------------

@router.get("/annotations/{annotation_id}/tissue-mask")
def get_annotation_tissue_mask(
    annotation_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """PNG (RGBA) de la máscara de tejido de la región de la anotación."""
    annotation, image = _get_annotation_ctx(db, annotation_id)
    try:
        analysis = annotation_analysis_service.get_or_create_tissue_mask(
            db, annotation, image.file_path, force=force
        )
        png_bytes = annotation_analysis_service.load_mask_png_bytes(analysis)
    except FileNotFoundError:
        analysis = annotation_analysis_service.generate_tissue_mask(
            db, annotation, image.file_path
        )
        png_bytes = annotation_analysis_service.load_mask_png_bytes(analysis)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en máscara de tejido de anotación: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generando máscara de tejido: {exc}",
        )
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get(
    "/annotations/{annotation_id}/tissue-mask/stats",
    response_model=AnalysisResultResponse,
)
def get_annotation_tissue_stats(
    annotation_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estadísticas del análisis de tejido de la anotación (JSON)."""
    annotation, image = _get_annotation_ctx(db, annotation_id)
    try:
        return annotation_analysis_service.get_or_create_tissue_mask(
            db, annotation, image.file_path, force=force
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en análisis de tejido de anotación: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en análisis de tejido: {exc}"
        )


@router.post(
    "/annotations/{annotation_id}/analyze/tissue",
    response_model=AnalysisResultResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_annotation_tissue(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fuerza el (re)análisis de tejido de la región anotada."""
    annotation, image = _get_annotation_ctx(db, annotation_id)
    try:
        return annotation_analysis_service.generate_tissue_mask(
            db, annotation, image.file_path
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en análisis de tejido de anotación: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en análisis de tejido: {exc}"
        )


@router.get("/annotations/{annotation_id}/density-map")
def get_annotation_density_map(
    annotation_id: int,
    grid_size: int = annotation_analysis_service.DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """PNG (RGBA) del heatmap de densidad de la región de la anotación."""
    _validate_density_params(grid_size, colormap)
    annotation, image = _get_annotation_ctx(db, annotation_id)
    try:
        density_map = annotation_analysis_service.get_or_create_density(
            db, annotation, image.file_path, grid_size, colormap, force=force
        )
        png_bytes = annotation_analysis_service.load_heatmap_png_bytes(
            density_map
        )
    except FileNotFoundError:
        density_map = annotation_analysis_service.generate_density(
            db, annotation, image.file_path, grid_size, colormap
        )
        png_bytes = annotation_analysis_service.load_heatmap_png_bytes(
            density_map
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en mapa de densidad de anotación: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generando mapa de densidad: {exc}",
        )
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get(
    "/annotations/{annotation_id}/density-map/stats",
    response_model=DensityMapResponse,
)
def get_annotation_density_stats(
    annotation_id: int,
    grid_size: int = annotation_analysis_service.DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Matriz de densidades y metadatos de la anotación (JSON)."""
    _validate_density_params(grid_size, colormap)
    annotation, image = _get_annotation_ctx(db, annotation_id)
    try:
        return annotation_analysis_service.get_or_create_density(
            db, annotation, image.file_path, grid_size, colormap, force=force
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en mapa de densidad de anotación: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en mapa de densidad: {exc}"
        )


@router.post(
    "/annotations/{annotation_id}/analyze/density",
    response_model=DensityMapResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_annotation_density(
    annotation_id: int,
    grid_size: int = annotation_analysis_service.DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fuerza la (re)generación del mapa de densidades de la anotación."""
    _validate_density_params(grid_size, colormap)
    annotation, image = _get_annotation_ctx(db, annotation_id)
    try:
        return annotation_analysis_service.generate_density(
            db, annotation, image.file_path, grid_size, colormap
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en mapa de densidad de anotación: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en mapa de densidad: {exc}"
        )


@router.post(
    "/annotations/{annotation_id}/analyze",
    response_model=FullAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_annotation(
    annotation_id: int,
    grid_size: int = annotation_analysis_service.DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Análisis completo (tejido + densidad) de la región anotada."""
    _validate_density_params(grid_size, colormap)
    annotation, image = _get_annotation_ctx(db, annotation_id)
    try:
        return annotation_analysis_service.run_full_analysis(
            db, annotation, image.file_path, grid_size, colormap
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en análisis consolidado de anotación: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en análisis consolidado: {exc}"
        )


@router.get(
    "/annotations/{annotation_id}/analysis",
    response_model=FullAnalysisResponse,
)
def get_annotation_analysis(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Último análisis consolidado de la anotación (404 si no existe)."""
    annotation = (
        db.query(Annotation).filter(Annotation.id == annotation_id).first()
    )
    if annotation is None:
        raise HTTPException(status_code=404, detail="Anotación no encontrada")
    analysis = annotation_analysis_service.get_full_analysis(db, annotation_id)
    if analysis is None:
        raise HTTPException(
            status_code=404, detail="La anotación no tiene análisis todavía"
        )
    return analysis


@router.get(
    "/annotations/{annotation_id}/analytics",
    response_model=AnalyticsResponse,
)
def get_annotation_analytics(
    annotation_id: int,
    spatial_bins: int = analytics_service.DEFAULT_SPATIAL_BINS,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Datos de analíticas de la región anotada (tejido + densidad por zonas)."""
    if spatial_bins < 2 or spatial_bins > 100:
        raise HTTPException(
            status_code=422, detail="spatial_bins debe estar entre 2 y 100"
        )
    annotation = (
        db.query(Annotation).filter(Annotation.id == annotation_id).first()
    )
    if annotation is None:
        raise HTTPException(status_code=404, detail="Anotación no encontrada")
    try:
        return annotation_analysis_service.build_annotation_analytics(
            db, annotation, spatial_bins=spatial_bins
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error generando analíticas de anotación: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error generando analíticas: {exc}"
        )


# --- Clasificación de tejido por IA (Sprint 7) ------------------------------


@router.get("/images/{image_id}/ai-classification")
def get_image_ai_classification(
    image_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """PNG (RGBA) del mapa de clases IA de la imagen. Lo genera si no existe."""
    image = _get_image_or_404(db, image_id)
    _ensure_file_exists(image)
    try:
        analysis = ai_classification_service.get_or_create_image_classification(
            db, image_id, image.file_path, force=force
        )
        png_bytes = ai_classification_service.load_map_png_bytes(analysis)
    except FileNotFoundError:
        analysis = ai_classification_service.generate_image_classification(
            db, image_id, image.file_path
        )
        png_bytes = ai_classification_service.load_map_png_bytes(analysis)
    except ai_classification_service.ModelUnavailableError as exc:
        logger.error(f"Modelo de IA no disponible: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en clasificación IA de imagen: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en clasificación IA: {exc}"
        )
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get(
    "/images/{image_id}/ai-classification/stats",
    response_model=AnalysisResultResponse,
)
def get_image_ai_classification_stats(
    image_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estadísticas de la clasificación IA de la imagen (JSON)."""
    image = _get_image_or_404(db, image_id)
    _ensure_file_exists(image)
    try:
        return ai_classification_service.get_or_create_image_classification(
            db, image_id, image.file_path, force=force
        )
    except ai_classification_service.ModelUnavailableError as exc:
        logger.error(f"Modelo de IA no disponible: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en clasificación IA de imagen: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en clasificación IA: {exc}"
        )


@router.post(
    "/images/{image_id}/analyze/ai",
    response_model=AnalysisResultResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_image_ai(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fuerza la (re)ejecución de la clasificación IA de la imagen."""
    image = _get_image_or_404(db, image_id)
    _ensure_file_exists(image)
    try:
        return ai_classification_service.generate_image_classification(
            db, image_id, image.file_path
        )
    except ai_classification_service.ModelUnavailableError as exc:
        logger.error(f"Modelo de IA no disponible: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en clasificación IA de imagen: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en clasificación IA: {exc}"
        )


@router.get("/annotations/{annotation_id}/ai-classification")
def get_annotation_ai_classification(
    annotation_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """PNG (RGBA) del mapa de clases IA de la región anotada."""
    annotation, image = _get_annotation_ctx(db, annotation_id)
    try:
        analysis = ai_classification_service.get_or_create_annotation_classification(
            db, annotation, image.file_path, force=force
        )
        png_bytes = ai_classification_service.load_map_png_bytes(analysis)
    except FileNotFoundError:
        analysis = ai_classification_service.generate_annotation_classification(
            db, annotation, image.file_path
        )
        png_bytes = ai_classification_service.load_map_png_bytes(analysis)
    except ai_classification_service.ModelUnavailableError as exc:
        logger.error(f"Modelo de IA no disponible: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en clasificación IA de anotación: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en clasificación IA: {exc}"
        )
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get(
    "/annotations/{annotation_id}/ai-classification/stats",
    response_model=AnalysisResultResponse,
)
def get_annotation_ai_classification_stats(
    annotation_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estadísticas de la clasificación IA de la anotación (JSON)."""
    annotation, image = _get_annotation_ctx(db, annotation_id)
    try:
        return ai_classification_service.get_or_create_annotation_classification(
            db, annotation, image.file_path, force=force
        )
    except ai_classification_service.ModelUnavailableError as exc:
        logger.error(f"Modelo de IA no disponible: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en clasificación IA de anotación: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en clasificación IA: {exc}"
        )


@router.post(
    "/annotations/{annotation_id}/analyze/ai",
    response_model=AnalysisResultResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_annotation_ai(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fuerza la (re)ejecución de la clasificación IA de la región anotada."""
    annotation, image = _get_annotation_ctx(db, annotation_id)
    try:
        return ai_classification_service.generate_annotation_classification(
            db, annotation, image.file_path
        )
    except ai_classification_service.ModelUnavailableError as exc:
        logger.error(f"Modelo de IA no disponible: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error en clasificación IA de anotación: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error en clasificación IA: {exc}"
        )
