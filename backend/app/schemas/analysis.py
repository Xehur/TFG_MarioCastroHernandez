"""
Esquemas Pydantic para resultados de análisis de imagen (Sprint 6).
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any


class TissueStats(BaseModel):
    """Estadísticas de la detección de tejido."""
    tissue_percent: float
    threshold_saturation: Optional[float] = None
    threshold_intensity: Optional[float] = None
    width: int
    height: int
    scale: Optional[float] = None
    method: Optional[str] = None


class AnalysisResultResponse(BaseModel):
    """Respuesta genérica de un resultado de análisis."""
    id: int
    image_id: int
    annotation_id: Optional[int] = None
    analysis_type: str
    result_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DensityMapResponse(BaseModel):
    """Respuesta de un mapa de densidades (matriz + metadatos)."""
    id: int
    image_id: int
    annotation_id: Optional[int] = None
    grid_size: int
    density_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FullAnalysisResponse(BaseModel):
    """Respuesta del análisis consolidado (tejido + densidad)."""
    id: int
    image_id: int
    annotation_id: Optional[int] = None
    analysis_type: str
    result_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnalyticsResponse(BaseModel):
    """Conjunto de datos de analíticas listos para gráficas y tablas."""
    image_id: int
    annotation_id: Optional[int] = None
    total_annotations: int
    by_type: list
    by_class: list
    distribution: list
    spatial: Dict[str, Any]
    tissue: Optional[Dict[str, Any]] = None
    density_zones: Optional[Dict[str, Any]] = None
