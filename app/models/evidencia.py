from pydantic import BaseModel
from typing import Optional


class EvidenciaResponse(BaseModel):
    id: str
    tarea_id: str
    usuario_id: str
    nombre_usuario: str
    urls: list[str]
    nombres: list[str]
    tipos: list[str]
    comentario: str
    created_at: str


class ActualizarEvidenciaComentarioRequest(BaseModel):
    comentario: Optional[str] = None
