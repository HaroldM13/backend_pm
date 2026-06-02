from pydantic import BaseModel, Field
from typing import Optional, Literal


Prioridad = Literal["critica", "alta", "media", "baja"]


TipoTarea = Literal["historia", "bug", "tarea", "mejora"]


class CrearTareaRequest(BaseModel):
    titulo: str = Field(min_length=2, max_length=200)
    descripcion: Optional[str] = Field(default=None, max_length=2000)
    proyecto_id: str
    columna: str = "backlog"
    asignado_a: Optional[str] = None
    prioridad: Prioridad = "media"
    horas_estimadas: float = Field(default=0, ge=0)
    fecha_inicio: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    etiquetas: list[str] = Field(default_factory=list)
    epica_id: Optional[str] = None
    sprint_id: Optional[str] = None
    tipo_tarea: TipoTarea = "tarea"
    puntos_historia: int = Field(default=0, ge=0)
    criterios_aceptacion: Optional[str] = Field(default=None, max_length=2000)


class ActualizarTareaRequest(BaseModel):
    titulo: Optional[str] = Field(default=None, min_length=2, max_length=200)
    descripcion: Optional[str] = None
    columna: Optional[str] = None
    asignado_a: Optional[str] = None
    prioridad: Optional[Prioridad] = None
    horas_estimadas: Optional[float] = Field(default=None, ge=0)
    fecha_inicio: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    etiquetas: Optional[list[str]] = None
    epica_id: Optional[str] = None
    sprint_id: Optional[str] = None
    tipo_tarea: Optional[TipoTarea] = None
    puntos_historia: Optional[int] = Field(default=None, ge=0)
    criterios_aceptacion: Optional[str] = None


class RegistrarHorasRequest(BaseModel):
    horas: float = Field(gt=0)
    descripcion: str = Field(min_length=1, max_length=500)
    fecha: str  # YYYY-MM-DD


class TareaResponse(BaseModel):
    id: str
    titulo: str
    descripcion: Optional[str] = None
    proyecto_id: str
    epica_id: Optional[str] = None
    sprint_id: Optional[str] = None
    columna: str
    asignado_a: Optional[str] = None
    creado_por: str
    prioridad: Prioridad
    horas_estimadas: float
    horas_registradas: float
    fecha_inicio: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    etiquetas: list[str]
    completada_en: Optional[str] = None
    created_at: str
    tipo_tarea: TipoTarea = "tarea"
    puntos_historia: int = 0
    criterios_aceptacion: Optional[str] = None


# ─── Actividad mensual ────────────────────────────────────────────────────────

class EntradaHoraActividad(BaseModel):
    fecha: str          # YYYY-MM-DD
    usuario_id: str
    horas: float
    tarea_id: str
    tarea_titulo: str
    descripcion: str


class TareaCompletadaActividad(BaseModel):
    fecha: str          # YYYY-MM-DD (día en que se completó)
    usuario_id: str     # quien la tenía asignada
    tarea_id: str
    titulo: str


class SprintActividad(BaseModel):
    id: str
    nombre: str
    fecha_inicio: str
    fecha_fin: str
    estado: str


class ActividadMensualResponse(BaseModel):
    horas: list[EntradaHoraActividad]
    completadas: list[TareaCompletadaActividad]
    sprints: list[SprintActividad]


class HoraLogResponse(BaseModel):
    id: str
    tarea_id: str
    usuario_id: str
    horas: float
    descripcion: str
    fecha: str
    created_at: str
