"""
Ejecutor de comandos del lado servidor (Sprint 6, issue 36).

Sólo los comandos con ``target == "backend"`` son ejecutables aquí. Cada uno se
resuelve mediante un manejador que reutiliza los servicios de análisis ya
existentes. Los comandos ``frontend`` se rechazan (los ejecuta la UI).
"""
import logging
import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.image import Image
from app.services.analysis import (
    analysis_service,
    tissue_service,
    density_service,
    ai_classification_service,
)
from app.services.commands import command_registry

logger = logging.getLogger(__name__)


class CommandError(Exception):
    """Error de ejecución de comando con un código HTTP asociado."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _require_image(
    db: Session, params: Dict[str, Any], user_id: Optional[int] = None
) -> Image:
    if "image_id" not in params or params["image_id"] in (None, ""):
        raise CommandError("Falta el parámetro obligatorio 'image_id'", 422)
    try:
        image_id = int(params["image_id"])
    except (TypeError, ValueError):
        raise CommandError("'image_id' debe ser un entero", 422)

    query = db.query(Image).filter(Image.id == image_id)
    if user_id is not None:
        # Solo imágenes del usuario que ejecuta el comando (404 si es ajena)
        query = query.filter(Image.user_id == user_id)
    image = query.first()
    if image is None:
        raise CommandError("Imagen no encontrada", 404)
    if not image.file_path or not os.path.exists(image.file_path):
        raise CommandError("Archivo de imagen no encontrado", 404)
    return image


def _run_full_analysis(
    db: Session, params: Dict[str, Any], user_id: Optional[int] = None
) -> Dict[str, Any]:
    image = _require_image(db, params, user_id)
    result = analysis_service.run_full_analysis(db, image.id, image.file_path)
    return {"analysis_id": result.id, "summary": result.result_data}


def _detect_tissue(
    db: Session, params: Dict[str, Any], user_id: Optional[int] = None
) -> Dict[str, Any]:
    image = _require_image(db, params, user_id)
    result = tissue_service.generate_tissue_mask(db, image.id, image.file_path)
    return {"analysis_id": result.id, "stats": result.result_data}


def _generate_density_map(
    db: Session, params: Dict[str, Any], user_id: Optional[int] = None
) -> Dict[str, Any]:
    image = _require_image(db, params, user_id)
    result = density_service.generate_density(db, image.id, image.file_path)
    data = result.density_data or {}
    return {
        "density_map_id": result.id,
        "grid_size": result.grid_size,
        "density_mean": data.get("density_mean"),
        "density_max": data.get("density_max"),
    }


def _classify_tissue_ai(
    db: Session, params: Dict[str, Any], user_id: Optional[int] = None
) -> Dict[str, Any]:
    image = _require_image(db, params, user_id)
    result = ai_classification_service.generate_image_classification(
        db, image.id, image.file_path
    )
    data = result.result_data or {}
    return {
        "analysis_id": result.id,
        "dominant_class": data.get("dominant_class"),
        "dominant_group": data.get("dominant_group"),
        "summary": data,
    }


_HANDLERS = {
    "run-full-analysis": _run_full_analysis,
    "detect-tissue": _detect_tissue,
    "generate-density-map": _generate_density_map,
    "classify-tissue-ai": _classify_tissue_ai,
}


def execute(
    db: Session,
    command_id: str,
    params: Dict[str, Any] | None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Ejecuta un comando de servidor y devuelve su resultado.

    Lanza ``CommandError`` con el código adecuado si el comando no existe, no es
    ejecutable en el servidor o faltan/parámetros inválidos.
    """
    params = params or {}
    command = command_registry.get_command(command_id)
    if command is None:
        raise CommandError(f"Comando '{command_id}' no encontrado", 404)

    if command["target"] != command_registry.TARGET_BACKEND:
        raise CommandError(
            f"El comando '{command_id}' se ejecuta en el frontend", 400
        )

    handler = _HANDLERS.get(command_id)
    if handler is None:  # defensivo: comando backend sin manejador
        raise CommandError(
            f"El comando '{command_id}' no tiene ejecución disponible", 400
        )

    result = handler(db, params, user_id)
    return {
        "command_id": command_id,
        "status": "success",
        "result": result,
    }
