"""
Esquemas Pydantic para la paleta de comandos (Sprint 6, issue 36).
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class CommandParam(BaseModel):
    name: str
    type: str
    required: bool
    description: str


class CommandInfo(BaseModel):
    id: str
    name: str
    description: str
    category: str
    icon: Optional[str] = None
    target: str
    method: Optional[str] = None
    endpoint: Optional[str] = None
    action: Optional[str] = None
    route: Optional[str] = None
    params: List[CommandParam] = []
    keywords: List[str] = []


class CommandListResponse(BaseModel):
    total: int
    categories: List[str]
    commands: List[CommandInfo]


class CommandExecuteRequest(BaseModel):
    command_id: str
    params: Optional[Dict[str, Any]] = None


class CommandExecuteResponse(BaseModel):
    command_id: str
    status: str
    result: Dict[str, Any]
