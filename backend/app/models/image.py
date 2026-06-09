from sqlalchemy import Column, Integer, String, DateTime, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True)
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