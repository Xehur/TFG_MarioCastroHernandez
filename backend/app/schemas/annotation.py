"""
Esquemas Pydantic para anotaciones y clases de anotación.
"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class ShapeType(str, Enum):
    rectangle = "rectangle"
    polygon = "polygon"
    circle = "circle"


# --- AnnotationClass ---------------------------------------------------------

class AnnotationClassBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#FF0000", max_length=32)
    description: Optional[str] = None


class AnnotationClassCreate(AnnotationClassBase):
    pass


class AnnotationClassResponse(AnnotationClassBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Annotation --------------------------------------------------------------

def _validate_coordinates(shape_type: str, coords: Dict[str, Any]) -> Dict[str, Any]:
    """Valida que las coordenadas coincidan con el tipo de forma."""
    if not isinstance(coords, dict):
        raise ValueError("coordinates debe ser un objeto")

    if shape_type == ShapeType.rectangle:
        required = {"x", "y", "width", "height"}
        if not required.issubset(coords):
            raise ValueError("rectangle requiere x, y, width, height")
    elif shape_type == ShapeType.circle:
        required = {"x", "y", "radius"}
        if not required.issubset(coords):
            raise ValueError("circle requiere x, y, radius")
    elif shape_type == ShapeType.polygon:
        points = coords.get("points")
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError("polygon requiere 'points' con al menos 3 vértices")
        for p in points:
            if not (isinstance(p, (list, tuple)) and len(p) == 2):
                raise ValueError("cada punto del polígono debe ser [x, y]")
    return coords


class AnnotationBase(BaseModel):
    shape_type: ShapeType
    coordinates: Dict[str, Any]
    label: Optional[str] = Field(default=None, max_length=255)
    color: str = Field(default="#FF0000", max_length=32)
    class_id: Optional[int] = None


class AnnotationCreate(AnnotationBase):
    @field_validator("coordinates")
    @classmethod
    def check_coordinates(cls, v, info):
        shape_type = info.data.get("shape_type")
        if shape_type is not None:
            return _validate_coordinates(shape_type, v)
        return v


class AnnotationUpdate(BaseModel):
    """Campos actualizables de una anotación (todos opcionales)."""
    shape_type: Optional[ShapeType] = None
    coordinates: Optional[Dict[str, Any]] = None
    label: Optional[str] = Field(default=None, max_length=255)
    color: Optional[str] = Field(default=None, max_length=32)
    class_id: Optional[int] = None


class AnnotationResponse(AnnotationBase):
    id: int
    image_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnnotationListResponse(BaseModel):
    total: int
    items: List[AnnotationResponse]


# --- COCO import/export ------------------------------------------------------

class COCOImportRequest(BaseModel):
    """Solicitud de importación COCO."""
    coco: Dict[str, Any] = Field(
        description="Documento COCO JSON completo (images, annotations, categories)."
    )
    category_mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description="Renombrado opcional {nombre_categoria_coco: nombre_clase_destino}.",
    )


class COCOImportResponse(BaseModel):
    """Resultado de una importación COCO."""
    imported: int
    created_classes: List[str]
    items: List[AnnotationResponse]
