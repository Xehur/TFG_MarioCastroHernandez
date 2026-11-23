from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base


class Image(Base):
    __tablename__ = "images"
    # El nombre de archivo es único POR USUARIO (dos usuarios pueden subir el
    # mismo nombre; cada uno tiene su carpeta en uploads/<user_id>/).
    __table_args__ = (
        UniqueConstraint("user_id", "filename", name="uq_images_user_filename"),
    )

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String)  # Ruta en servidor, NO datos binarios
    user_id = Column(Integer, index=True)

    # Metadatos WSI (pequeños, valen en BD)
    width = Column(Integer)
    height = Column(Integer)
    level_count = Column(Integer)
    downsamples = Column(JSON)
    properties = Column(JSON)
    file_size_mb = Column(Float)  # Tamaño en MB

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    analysis_results = relationship(
        "AnalysisResult",
        back_populates="image",
        cascade="all, delete-orphan",
    )
    density_maps = relationship(
        "DensityMap",
        back_populates="image",
        cascade="all, delete-orphan",
    )