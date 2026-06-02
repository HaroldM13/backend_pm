from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from bson import ObjectId
import uuid

from ..database import get_db
from ..dependencies import get_current_user
from ..utils.helpers import fecha_a_str
from ..models.checklist import (
    ChecklistResponse, ChecklistItem, CrearChecklistRequest, ActualizarChecklistRequest,
)

router = APIRouter()


def _checklist_a_response(doc: dict) -> ChecklistResponse:
    items = [
        ChecklistItem(id=it["id"], texto=it["texto"], completado=it.get("completado", False))
        for it in doc.get("items", [])
    ]
    return ChecklistResponse(
        id=str(doc["_id"]),
        tarea_id=doc["tarea_id"],
        nombre=doc["nombre"],
        items=items,
        created_at=fecha_a_str(doc["created_at"]),
    )


async def _verificar_acceso_tarea(db: AsyncIOMotorDatabase, tarea_id: str, usuario_id: str) -> dict:
    try:
        tarea = await db.tareas.find_one({"_id": ObjectId(tarea_id)})
    except Exception:
        tarea = None
    if not tarea:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada")
    proyecto = await db.proyectos.find_one({"_id": ObjectId(tarea["proyecto_id"]), "miembros": usuario_id})
    if not proyecto:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return tarea


@router.get("/tarea/{tarea_id}", response_model=list[ChecklistResponse])
async def listar_checklists(
    tarea_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    await _verificar_acceso_tarea(db, tarea_id, usuario["id"])
    docs = await db.checklists.find({"tarea_id": tarea_id}).sort("created_at", 1).to_list(50)
    return [_checklist_a_response(d) for d in docs]


@router.post("/tarea/{tarea_id}", response_model=ChecklistResponse, status_code=status.HTTP_201_CREATED)
async def crear_checklist(
    tarea_id: str,
    datos: CrearChecklistRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    await _verificar_acceso_tarea(db, tarea_id, usuario["id"])

    ahora = datetime.now(timezone.utc)
    items = [
        {"id": str(uuid.uuid4()), "texto": it.texto, "completado": False}
        for it in (datos.items or [])
    ]
    doc = {
        "tarea_id": tarea_id,
        "nombre": datos.nombre,
        "items": items,
        "created_at": ahora,
    }
    resultado = await db.checklists.insert_one(doc)
    doc["_id"] = resultado.inserted_id
    return _checklist_a_response(doc)


@router.patch("/{checklist_id}", response_model=ChecklistResponse)
async def actualizar_checklist(
    checklist_id: str,
    datos: ActualizarChecklistRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    try:
        doc = await db.checklists.find_one({"_id": ObjectId(checklist_id)})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist no encontrado")

    await _verificar_acceso_tarea(db, doc["tarea_id"], usuario["id"])

    cambios: dict = {}
    if datos.nombre is not None:
        cambios["nombre"] = datos.nombre
    if datos.items is not None:
        cambios["items"] = [
            {
                "id": it.id if it.id else str(uuid.uuid4()),
                "texto": it.texto,
                "completado": it.completado,
            }
            for it in datos.items
        ]

    if cambios:
        await db.checklists.update_one({"_id": ObjectId(checklist_id)}, {"$set": cambios})
        doc.update(cambios)

    return _checklist_a_response(doc)


@router.delete("/{checklist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_checklist(
    checklist_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    try:
        doc = await db.checklists.find_one({"_id": ObjectId(checklist_id)})
    except Exception:
        doc = None
    if not doc:
        return

    await _verificar_acceso_tarea(db, doc["tarea_id"], usuario["id"])
    await db.checklists.delete_one({"_id": ObjectId(checklist_id)})
