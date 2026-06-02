from pydantic import BaseModel, Field
from typing import Optional, Literal


SubtipoMensaje = Literal["texto", "imagen", "archivo", "tarea"]


class EnviarMensajeWs(BaseModel):
    contenido: str = Field(min_length=1, max_length=5000)
    menciones: list[str] = Field(default_factory=list)
    reply_to_id: Optional[str] = None


class MensajeResponse(BaseModel):
    id: str
    sala_id: str
    remitente_id: str
    nombre_remitente: str
    contenido: str
    subtipo: SubtipoMensaje
    archivo_url: Optional[str] = None
    archivo_nombre: Optional[str] = None
    archivo_tamano: Optional[int] = None
    menciones: list[str]
    # Reply
    reply_to_id: Optional[str] = None
    reply_to_preview: Optional[str] = None       # texto truncado del mensaje citado
    reply_to_remitente: Optional[str] = None     # nombre de quien escribió el original
    # Tarea compartida
    tarea_id: Optional[str] = None
    tarea_titulo: Optional[str] = None
    tarea_columna: Optional[str] = None
    tarea_prioridad: Optional[str] = None
    tarea_proyecto_id: Optional[str] = None
    created_at: str


class SalaChatResponse(BaseModel):
    id: str
    nombre: str
    tipo: Literal["area", "proyecto", "directo", "grupo"]
    referencia_id: Optional[str] = None
    miembros: list[str]
    created_at: str


class CrearGrupoRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    miembro_ids: list[str] = Field(default_factory=list)


class CompartirTareaRequest(BaseModel):
    tarea_id: str
    tarea_titulo: str
    tarea_columna: str
    tarea_prioridad: str
    tarea_proyecto_id: Optional[str] = None
    comentario: str = Field(default="", max_length=1000)
    menciones: list[str] = Field(default_factory=list)
