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
    width: int
    height: int
    level_count: int
    downsamples: List[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True