"""
Modelos de resultados de análisis de imagen (Sprint 6).

- AnalysisResult: resultado genérico de un análisis sobre una imagen
  (p.ej. detección de tejido). ``result_data`` guarda un JSON con las
  métricas y metadatos del análisis (porcentaje de tejido, umbral, ruta de
  la máscara cacheada, dimensiones de trabajo, etc.).
- DensityMap: mapa de densidades por celdas de un grid configurable.
  ``density_data`` guarda la matriz de densidades y sus metadatos.

Ambos son la base para las funcionalidades de análisis de tejido y de mapas
de densidad. El campo JSON permite evolucionar el contenido (p.ej. añadir
resultados de modelos de IA en el futuro) sin cambiar el esquema.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(
        Integer, ForeignKey("images.id"), index=True, nullable=False
    )
    # Si el análisis es sobre una anotación (zona marcada) en vez de sobre la
    # imagen completa, apunta a dicha anotación. NULL = análisis de imagen.
    annotation_id = Column(
        Integer,
        ForeignKey("annotations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    # p.ej. "tissue_mask", "density_map", "full_analysis"
    analysis_type = Column(String, nullable=False, index=True)
    # Métricas y metadatos del análisis (estructura según analysis_type)
    result_data = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    image = relationship("Image", back_populates="analysis_results")

    def __repr__(self):
        return (
            f"AnalysisResult(id={self.id}, type={self.analysis_type}, "
            f"image_id={self.image_id})"
        )


class DensityMap(Base):
    __tablename__ = "density_maps"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(
        Integer, ForeignKey("images.id"), index=True, nullable=False
    )
    # Si el mapa es sobre una anotación (zona marcada) en vez de sobre la
    # imagen completa, apunta a dicha anotación. NULL = mapa de imagen.
    annotation_id = Column(
        Integer,
        ForeignKey("annotations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    # Tamaño de celda del grid en píxeles de la imagen base
    grid_size = Column(Integer, nullable=False)
    # Matriz de densidades y metadatos (filas, columnas, min, max, colormap...)
    density_data = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    image = relationship("Image", back_populates="density_maps")

    def __repr__(self):
        return (
            f"DensityMap(id={self.id}, grid_size={self.grid_size}, "
            f"image_id={self.image_id})"
        )
