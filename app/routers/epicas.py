from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from bson import ObjectId
from ..database import get_db
from ..dependencies import get_current_user
from ..models.epica import CrearEpicaRequest, ActualizarEpicaRequest, EpicaResponse
from ..utils.helpers import fecha_a_str

router = APIRouter()


def _epica_a_response(doc: dict) -> EpicaResponse:
    return EpicaResponse(
        id=str(doc["_id"]),
        proyecto_id=doc["proyecto_id"],
        nombre=doc["nombre"],
        descripcion=doc.get("descripcion"),
        color=doc.get("color", "#6366F1"),
        created_at=fecha_a_str(doc["created_at"]),
    )


async def _verificar_acceso(db: AsyncIOMotorDatabase, proyecto_id: str, usuario_id: str) -> None:
    try:
        proyecto = await db.proyectos.find_one({"_id": ObjectId(proyecto_id), "miembros": usuario_id})
    except Exception:
        proyecto = None
    if not proyecto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")


@router.get("/proyecto/{proyecto_id}", response_model=list[EpicaResponse])
async def listar_epicas(
    proyecto_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    await _verificar_acceso(db, proyecto_id, usuario["id"])
    docs = await db.epicas.find({"proyecto_id": proyecto_id}).sort("created_at", 1).to_list(length=100)
    return [_epica_a_response(d) for d in docs]


@router.post("/proyecto/{proyecto_id}", response_model=EpicaResponse, status_code=status.HTTP_201_CREATED)
async def crear_epica(
    proyecto_id: str,
    datos: CrearEpicaRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    await _verificar_acceso(db, proyecto_id, usuario["id"])

    doc = {
        "proyecto_id": proyecto_id,
        "nombre": datos.nombre,
        "descripcion": datos.descripcion,
        "color": datos.color,
        "created_at": datetime.now(timezone.utc),
    }
    resultado = await db.epicas.insert_one(doc)
    doc["_id"] = resultado.inserted_id
    return _epica_a_response(doc)


@router.patch("/{epica_id}", response_model=EpicaResponse)
async def actualizar_epica(
    epica_id: str,
    datos: ActualizarEpicaRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    doc = await db.epicas.find_one({"_id": ObjectId(epica_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Épica no encontrada")

    await _verificar_acceso(db, doc["proyecto_id"], usuario["id"])

    cambios = {k: v for k, v in datos.model_dump().items() if v is not None}
    if cambios:
        await db.epicas.update_one({"_id": ObjectId(epica_id)}, {"$set": cambios})
        doc.update(cambios)

    return _epica_a_response(doc)


@router.delete("/{epica_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_epica(
    epica_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    doc = await db.epicas.find_one({"_id": ObjectId(epica_id)})
    if not doc:
        return

    await _verificar_acceso(db, doc["proyecto_id"], usuario["id"])
    await db.epicas.delete_one({"_id": ObjectId(epica_id)})
    # Desvincular tareas de esta épica
    await db.tareas.update_many({"epica_id": epica_id}, {"$set": {"epica_id": None}})
