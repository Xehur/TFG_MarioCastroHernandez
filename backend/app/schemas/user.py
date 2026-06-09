"""
Esquemas Pydantic para User
"""
from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True