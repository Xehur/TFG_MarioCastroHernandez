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
    analysis_type: str
    result_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
