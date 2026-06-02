from pydantic import BaseModel, Field
from typing import Optional


class CrearProyectoRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    area_id: str


class ActualizarProyectoRequest(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)


class AgregarMiembroProyectoRequest(BaseModel):
    email: Optional[str] = None
    telefono: Optional[str] = None


class ColumnaCustom(BaseModel):
    id: str
    nombre: str = Field(min_length=1, max_length=50)
    orden: int = 10
    color: str = "indigo"


class GestionarColumnasRequest(BaseModel):
    columnas: list[ColumnaCustom]


class ProyectoResponse(BaseModel):
    id: str
    nombre: str
    descripcion: Optional[str] = None
    area_id: str
    creador_id: str
    miembros: list[str]
    chat_grupo_id: Optional[str] = None
    sprint_activo_id: Optional[str] = None
    columnas_custom: list[ColumnaCustom] = Field(default_factory=list)
    created_at: str
