from pydantic import BaseModel, Field
from typing import Optional


class CrearEpicaRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    color: str = Field(default="#6366F1", pattern=r"^#[0-9A-Fa-f]{6}$")


class ActualizarEpicaRequest(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    descripcion: Optional[str] = None
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class EpicaResponse(BaseModel):
    id: str
    proyecto_id: str
    nombre: str
    descripcion: Optional[str] = None
    color: str
    created_at: str
