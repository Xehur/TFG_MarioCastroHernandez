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


@router.get("/ai")
def ai_status():
    """
    Estado del motor de IA: dispositivo configurado (AI_DEVICE) y el que se usa
    realmente, versión de PyTorch y GPU detectada. No carga el modelo, así que
    sirve para comprobar tras montar la app con Docker si la GPU es visible.
    """
    import os

    from app.config import settings
    from app.services.analysis import inception_classifier as ic

    loaded = ic._classifier
    gpu = ic.gpu_info()
    return {
        "requested_device": settings.AI_DEVICE,
        "device": loaded.device if loaded else ic._resolve_device(settings.AI_DEVICE),
        "model_loaded": loaded is not None,
        "weights_found": os.path.isfile(settings.INCEPTION_WEIGHTS_PATH),
        **gpu,
    }
