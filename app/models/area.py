from pydantic import BaseModel, Field
from typing import Optional


class CrearAreaRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)


class ActualizarAreaRequest(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)


class AgregarMiembroRequest(BaseModel):
    email: Optional[str] = None
    telefono: Optional[str] = None


class AreaResponse(BaseModel):
    id: str
    nombre: str
    descripcion: Optional[str] = None
    creador_id: str
    miembros: list[str]
    chat_grupo_id: Optional[str] = None
    created_at: str
