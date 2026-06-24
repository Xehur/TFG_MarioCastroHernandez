"""
Modelos de anotaciones para imágenes WSI.

- AnnotationClass: clases configurables para clasificar anotaciones
  (p.ej. "Tumor", "Necrosis", "Estroma").
- Annotation: una forma dibujada sobre una imagen (rectángulo, polígono o
  círculo) con su etiqueta, color y clasificación opcional.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db import Base


class AnnotationClass(Base):
    __tablename__ = "annotation_classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    color = Column(String, nullable=False, default="#FF0000")
    description = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    annotations = relationship("Annotation", back_populates="annotation_class")

    def __repr__(self):
        return f"AnnotationClass(id={self.id}, name={self.name})"


class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # rectangle | polygon | circle
    shape_type = Column(String, nullable=False)
    # Coordenadas en píxeles de la imagen (estructura según shape_type)
    coordinates = Column(JSON, nullable=False)
    label = Column(String, nullable=True)
    color = Column(String, nullable=False, default="#FF0000")

    class_id = Column(
        Integer, ForeignKey("annotation_classes.id"), index=True, nullable=True
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    annotation_class = relationship("AnnotationClass", back_populates="annotations")

    def __repr__(self):
        return f"Annotation(id={self.id}, shape={self.shape_type}, image_id={self.image_id})"
