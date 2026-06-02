from pydantic import BaseModel, Field
from typing import Optional


class ChecklistItemInput(BaseModel):
    id: Optional[str] = None
    texto: str = Field(min_length=1, max_length=500)
    completado: bool = False


class ChecklistItem(BaseModel):
    id: str
    texto: str
    completado: bool


class CrearChecklistRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    items: list[ChecklistItemInput] = Field(default_factory=list)


class ActualizarChecklistRequest(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=200)
    items: Optional[list[ChecklistItemInput]] = None


class ChecklistResponse(BaseModel):
    id: str
    tarea_id: str
    nombre: str
    items: list[ChecklistItem]
    created_at: str
