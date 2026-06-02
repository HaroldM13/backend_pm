from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..database import get_db
from ..dependencies import get_current_user
from ..models.estado import EstadoResponse
from ..services.imagen_service import guardar_imagen
from ..utils.helpers import fecha_a_str

router = APIRouter()

_DURACION_MINUTOS = 5


def _estado_a_response(doc: dict, usuario_id: str) -> EstadoResponse:
    return EstadoResponse(
        id=str(doc["_id"]),
        usuario_id=doc["usuario_id"],
        nombre_usuario=doc.get("nombre_usuario", ""),
        url_imagen=doc["url_imagen"],
        created_at=fecha_a_str(doc["created_at"]),
        expira_at=fecha_a_str(doc["expira_at"]),
        es_propio=doc["usuario_id"] == usuario_id,
    )


@router.get("/", response_model=list[EstadoResponse])
async def listar_estados(
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    ahora = datetime.now(timezone.utc)
    docs = await db.estados.find(
        {"expira_at": {"$gt": ahora}}
    ).sort("created_at", -1).to_list(length=200)
    return [_estado_a_response(d, usuario["id"]) for d in docs]


@router.post("/", response_model=EstadoResponse, status_code=status.HTTP_201_CREATED)
async def crear_estado(
    archivo: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    url = await guardar_imagen(archivo, usuario["id"])
    ahora = datetime.now(timezone.utc)
    expira = ahora + timedelta(minutes=_DURACION_MINUTOS)

    doc = {
        "usuario_id": usuario["id"],
        "nombre_usuario": usuario["nombre"],
        "url_imagen": url,
        "created_at": ahora,
        "expira_at": expira,
    }
    resultado = await db.estados.insert_one(doc)
    doc["_id"] = resultado.inserted_id
    return _estado_a_response(doc, usuario["id"])


@router.delete("/{estado_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_estado(
    estado_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(estado_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estado no encontrado")

    doc = await db.estados.find_one({"_id": oid, "usuario_id": usuario["id"]})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estado no encontrado")

    await db.estados.delete_one({"_id": oid})
