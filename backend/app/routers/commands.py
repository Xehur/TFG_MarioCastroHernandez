"""
Router de la paleta de comandos (Sprint 6, issue 36).

Endpoints:
- GET  /commands            lista de comandos (filtro por texto y categoría)
- GET  /commands/categories categorías disponibles
- POST /commands/execute    ejecuta un comando del lado servidor
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.command import (
    CommandListResponse,
    CommandExecuteRequest,
    CommandExecuteResponse,
)
from app.services.commands import command_registry, command_executor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/commands", tags=["commands"])


@router.get("", response_model=CommandListResponse)
def list_commands(
    q: Optional[str] = None,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Devuelve los comandos disponibles, con filtro opcional de texto/categoría."""
    commands = command_registry.list_commands(query=q, category=category)
    return {
        "total": len(commands),
        "categories": command_registry.list_categories(),
        "commands": commands,
    }


@router.get("/categories")
def list_categories(current_user: User = Depends(get_current_user)):
    """Devuelve las categorías de comandos disponibles."""
    return {"categories": command_registry.list_categories()}


@router.post("/execute", response_model=CommandExecuteResponse)
def execute_command(
    payload: CommandExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ejecuta un comando de servidor y devuelve su resultado."""
    try:
        return command_executor.execute(db, payload.command_id, payload.params)
    except command_executor.CommandError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error ejecutando comando '{payload.command_id}': {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error ejecutando comando: {exc}"
        )
