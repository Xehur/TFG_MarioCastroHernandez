from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict


class ImageBase(BaseModel):
    filename: str
    user_id: int


class ImageCreate(ImageBase):
    pass


class ImageResponse(ImageBase):
    id: int
    file_path: str
    width: Optional[int] = None
    height: Optional[int] = None
    level_count: Optional[int] = None
    downsamples: Optional[List[float]] = None
    properties: Optional[Dict] = None
    file_size_mb: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ImageUploadResult(BaseModel):
    """Resultado del upload de un archivo individual"""
    filename: str
    success: bool
    message: str
    image: Optional[ImageResponse] = None
    error: Optional[str] = None


class MultipleUploadResponse(BaseModel):
    """Respuesta para upload de múltiples archivos"""
    total: int
    successful: int
    failed: int
    results: List[ImageUploadResult]