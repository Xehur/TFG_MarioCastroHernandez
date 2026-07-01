"""
Servicio de análisis consolidado en tiempo real (Sprint 6, issue 37).

Orquesta en una sola operación la detección de tejido y la generación del mapa
de densidades reutilizando ``tissue_service`` y ``density_service``, y persiste
un resultado consolidado (``AnalysisResult`` con analysis_type="full_analysis")
que resume ambos análisis para el panel de resultados del frontend.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.analysis import AnalysisResult
from app.services.analysis import tissue_service, density_service
from app.services.analysis.density_generation import DEFAULT_COLORMAP

logger = logging.getLogger(__name__)

FULL_ANALYSIS_TYPE = "full_analysis"


def get_full_analysis(db: Session, image_id: int) -> Optional[AnalysisResult]:
    """Devuelve el análisis consolidado más reciente de la imagen, si existe."""
    return (
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.image_id == image_id,
            AnalysisResult.analysis_type == FULL_ANALYSIS_TYPE,
        )
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )


def _build_summary(tissue_data: dict, density_data: dict, grid_size: int,
                   colormap: str) -> dict:
    """Compone el resumen serializable del análisis consolidado."""
    return {
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


def run_full_analysis(
    db: Session,
    image_id: int,
    file_path: str,
    grid_size: int = density_service.DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
) -> AnalysisResult:
    """
    Ejecuta el análisis completo (tejido + densidad) y persiste (o actualiza)
    el ``AnalysisResult`` consolidado. Devuelve dicho registro.
    """
    tissue = tissue_service.generate_tissue_mask(db, image_id, file_path)
    density = density_service.generate_density(
        db, image_id, file_path, grid_size=grid_size, colormap=colormap
    )

    summary = _build_summary(
        tissue.result_data or {},
        density.density_data or {},
        grid_size,
        colormap,
    )

    existing = get_full_analysis(db, image_id)
    if existing is not None:
        existing.result_data = summary
        db.commit()
        db.refresh(existing)
        return existing

    analysis = AnalysisResult(
        image_id=image_id,
        analysis_type=FULL_ANALYSIS_TYPE,
        result_data=summary,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis
