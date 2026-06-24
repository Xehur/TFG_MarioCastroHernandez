"""
Esquemas Pydantic para User y autenticación
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserRegister(BaseModel):
    """Datos para registrar un nuevo usuario."""
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """Datos para iniciar sesión."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Respuesta de autenticación con el token de acceso."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse