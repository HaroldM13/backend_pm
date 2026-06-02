from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from bson import ObjectId
from ..database import get_db
from ..dependencies import get_current_user
from ..models.sprint import CrearSprintRequest, ActualizarSprintRequest, SprintResponse
from ..utils.helpers import fecha_a_str
from ..websocket.manager import manager

router = APIRouter()


def _sprint_a_response(doc: dict) -> SprintResponse:
    return SprintResponse(
        id=str(doc["_id"]),
        proyecto_id=doc["proyecto_id"],
        nombre=doc["nombre"],
        objetivo=doc.get("objetivo"),
        fecha_inicio=doc["fecha_inicio"],
        fecha_fin=doc["fecha_fin"],
        estado=doc["estado"],
        color=doc.get("color", "indigo"),
        created_at=fecha_a_str(doc["created_at"]),
    )


async def _verificar_acceso_proyecto(db: AsyncIOMotorDatabase, proyecto_id: str, usuario_id: str) -> dict:
    try:
        proyecto = await db.proyectos.find_one({"_id": ObjectId(proyecto_id), "miembros": usuario_id})
    except Exception:
        proyecto = None
    if not proyecto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    return proyecto


@router.get("/proyecto/{proyecto_id}", response_model=list[SprintResponse])
async def listar_sprints(
    proyecto_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    await _verificar_acceso_proyecto(db, proyecto_id, usuario["id"])
    docs = await db.sprints.find({"proyecto_id": proyecto_id}).sort("created_at", -1).to_list(length=50)
    return [_sprint_a_response(d) for d in docs]


@router.post("/proyecto/{proyecto_id}", response_model=SprintResponse, status_code=status.HTTP_201_CREATED)
async def crear_sprint(
    proyecto_id: str,
    datos: CrearSprintRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    await _verificar_acceso_proyecto(db, proyecto_id, usuario["id"])

    ahora = datetime.now(timezone.utc)
    doc = {
        "proyecto_id": proyecto_id,
        "nombre": datos.nombre,
        "objetivo": datos.objetivo,
        "fecha_inicio": datos.fecha_inicio,
        "fecha_fin": datos.fecha_fin,
        "estado": "planificado",
        "color": datos.color,
        "created_at": ahora,
    }
    resultado = await db.sprints.insert_one(doc)
    doc["_id"] = resultado.inserted_id
    return _sprint_a_response(doc)


@router.post("/{sprint_id}/iniciar", response_model=SprintResponse)
async def iniciar_sprint(
    sprint_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    doc = await db.sprints.find_one({"_id": ObjectId(sprint_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint no encontrado")

    proyecto = await _verificar_acceso_proyecto(db, doc["proyecto_id"], usuario["id"])

    # Solo un sprint activo por proyecto
    activo = await db.sprints.find_one({"proyecto_id": doc["proyecto_id"], "estado": "activo"})
    if activo:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya hay un sprint activo en este proyecto")

    await db.sprints.update_one({"_id": ObjectId(sprint_id)}, {"$set": {"estado": "activo"}})
    await db.proyectos.update_one({"_id": ObjectId(doc["proyecto_id"])}, {"$set": {"sprint_activo_id": sprint_id}})
    doc["estado"] = "activo"

    # Notificar en el canal del proyecto
    if proyecto.get("chat_grupo_id"):
        ahora = datetime.now(timezone.utc)
        msg = f"🚀 Sprint **{doc['nombre']}** iniciado — {doc['fecha_inicio']} al {doc['fecha_fin']}"
        doc_msg = {
            "sala_id": proyecto["chat_grupo_id"],
            "remitente_id": "sistema",
            "nombre_remitente": "Sistema",
            "contenido": msg,
            "subtipo": "texto",
            "menciones": [],
            "created_at": ahora,
        }
        resultado_msg = await db.mensajes.insert_one(doc_msg)
        await manager.broadcast(proyecto["chat_grupo_id"], {
            "id": str(resultado_msg.inserted_id),
            "sala_id": proyecto["chat_grupo_id"],
            "remitente_id": "sistema",
            "nombre_remitente": "Sistema",
            "contenido": msg,
            "subtipo": "texto",
            "menciones": [],
            "created_at": fecha_a_str(ahora),
        })

    return _sprint_a_response(doc)


@router.post("/{sprint_id}/completar", response_model=SprintResponse)
async def completar_sprint(
    sprint_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    doc = await db.sprints.find_one({"_id": ObjectId(sprint_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint no encontrado")

    await _verificar_acceso_proyecto(db, doc["proyecto_id"], usuario["id"])

    if doc["estado"] != "activo":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solo se puede completar un sprint que esté activo")

    # Bloquear si hay tareas sin completar en el sprint
    pendientes = await db.tareas.count_documents({"sprint_id": sprint_id, "columna": {"$ne": "done"}})
    if pendientes > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hay {pendientes} tarea(s) sin completar en el sprint. Muévelas a 'Completada' o quítalas del sprint antes de cerrar.",
        )

    await db.sprints.update_one({"_id": ObjectId(sprint_id)}, {"$set": {"estado": "completado"}})
    await db.proyectos.update_one({"_id": ObjectId(doc["proyecto_id"])}, {"$set": {"sprint_activo_id": None}})
    doc["estado"] = "completado"

    return _sprint_a_response(doc)


@router.patch("/{sprint_id}", response_model=SprintResponse)
async def actualizar_sprint(
    sprint_id: str,
    datos: ActualizarSprintRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    doc = await db.sprints.find_one({"_id": ObjectId(sprint_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint no encontrado")

    await _verificar_acceso_proyecto(db, doc["proyecto_id"], usuario["id"])

    if doc["estado"] == "completado":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede editar un sprint completado")

    cambios = {k: v for k, v in datos.model_dump().items() if v is not None}
    if not cambios:
        return _sprint_a_response(doc)

    await db.sprints.update_one({"_id": ObjectId(sprint_id)}, {"$set": cambios})
    doc.update(cambios)
    return _sprint_a_response(doc)


@router.delete("/{sprint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_sprint(
    sprint_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    doc = await db.sprints.find_one({"_id": ObjectId(sprint_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint no encontrado")

    await _verificar_acceso_proyecto(db, doc["proyecto_id"], usuario["id"])

    if doc["estado"] != "planificado":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solo se pueden eliminar sprints en estado 'Planificado'")

    # Desasociar las tareas que tuvieran este sprint
    await db.tareas.update_many({"sprint_id": sprint_id}, {"$set": {"sprint_id": None}})
    await db.sprints.delete_one({"_id": ObjectId(sprint_id)})
