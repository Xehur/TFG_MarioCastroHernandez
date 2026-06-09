"""
Middleware personalizado para la aplicación
"""
import logging
import time
from typing import Callable
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("app")


async def add_process_time_header(request: Request, call_next: Callable):
    """
    Middleware que añade el tiempo de procesamiento a la respuesta
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)

    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s"
    )

    return response


async def error_handler(request: Request, exc: Exception):
    """
    Manejador global de errores
    """
    logger.error(f"Error en {request.url.path}: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor",
            "error": str(exc) if request.app.debug else "Internal Server Error"
        }
    )