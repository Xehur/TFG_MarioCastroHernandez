"""
Router para endpoints de salud y verificación
"""
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    """
    Endpoint de verificación de salud de la API
    """
    return {
        "status": "healthy",
        "service": "WSI Backend API"
    }


@router.get("/live")
async def liveness():
    """
    Endpoint de liveness - verifica que la aplicación está viva
    """
    return {
        "status": "alive",
        "service": "WSI Backend API"
    }


@router.get("/ready")
async def readiness():
    """
    Endpoint de readiness - verifica que la aplicación está lista
    """
    return {
        "status": "ready",
        "service": "WSI Backend API"
    }