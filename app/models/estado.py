from pydantic import BaseModel


class EstadoResponse(BaseModel):
    id: str
    usuario_id: str
    nombre_usuario: str
    url_imagen: str
    created_at: str
    expira_at: str
    es_propio: bool = False
