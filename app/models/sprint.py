from pydantic import BaseModel, Field
from typing import Optional, Literal


EstadoSprint = Literal["planificado", "activo", "completado"]


class CrearSprintRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    objetivo: Optional[str] = Field(default=None, max_length=500)
    fecha_inicio: str  # YYYY-MM-DD
    fecha_fin: str
    color: str = "indigo"


class ActualizarSprintRequest(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    objetivo: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    color: Optional[str] = None


class SprintResponse(BaseModel):
    id: str
    proyecto_id: str
    nombre: str
    objetivo: Optional[str] = None
    fecha_inicio: str
    fecha_fin: str
    estado: EstadoSprint
    color: str = "indigo"
    created_at: str
