from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone
from ..database import get_db
from ..dependencies import get_current_user
from ..models.usuario import (
    UsuarioResponse, ActualizarPerfilRequest,
    HorarioTrabajo, ActualizarHorarioRequest, ToggleDisponibleRequest,
)
from ..utils.helpers import fecha_a_str

router = APIRouter()


def _esta_disponible(doc: dict) -> bool:
    horario = doc.get("horario_trabajo")
    if not horario or not horario.get("activo"):
        return True
    if horario.get("disponible_manual"):
        return True
    ahora = datetime.now(timezone.utc)
    # weekday(): 0=Lunes … 6=Domingo
    if ahora.weekday() not in horario.get("dias", []):
        return False
    try:
        h_ini = list(map(int, horario["hora_inicio"].split(":")))
        h_fin = list(map(int, horario["hora_fin"].split(":")))
        minutos_ahora = ahora.hour * 60 + ahora.minute
        minutos_ini = h_ini[0] * 60 + h_ini[1]
        minutos_fin = h_fin[0] * 60 + h_fin[1]
        return minutos_ini <= minutos_ahora <= minutos_fin
    except Exception:
        return True


def _doc_a_response(doc: dict) -> UsuarioResponse:
    horario_raw = doc.get("horario_trabajo")
    horario = HorarioTrabajo(**horario_raw) if horario_raw else None
    return UsuarioResponse(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
        email=doc["email"],
        telefono=doc["telefono"],
        avatar_url=doc.get("avatar_url"),
        created_at=fecha_a_str(doc["created_at"]),
        horario_trabajo=horario,
        disponible=_esta_disponible(doc),
    )


@router.get("/", response_model=list[UsuarioResponse])
async def listar_usuarios(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    docs = await db.usuarios.find({}, {"password_hash": 0}).to_list(length=500)
    return [_doc_a_response(d) for d in docs]


@router.get("/perfil", response_model=UsuarioResponse)
async def obtener_perfil(
    usuario: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc = await db.usuarios.find_one({"_id": ObjectId(usuario["id"])}, {"password_hash": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return _doc_a_response(doc)


@router.patch("/perfil", response_model=UsuarioResponse)
async def actualizar_perfil(
    datos: ActualizarPerfilRequest,
    usuario: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cambios = {k: v for k, v in datos.model_dump().items() if v is not None}
    if cambios:
        await db.usuarios.update_one({"_id": ObjectId(usuario["id"])}, {"$set": cambios})
    doc = await db.usuarios.find_one({"_id": ObjectId(usuario["id"])}, {"password_hash": 0})
    return _doc_a_response(doc)


@router.patch("/horario", response_model=UsuarioResponse)
async def actualizar_horario(
    datos: ActualizarHorarioRequest,
    usuario: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    await db.usuarios.update_one(
        {"_id": ObjectId(usuario["id"])},
        {"$set": {"horario_trabajo": datos.horario_trabajo.model_dump()}},
    )
    doc = await db.usuarios.find_one({"_id": ObjectId(usuario["id"])}, {"password_hash": 0})
    return _doc_a_response(doc)


@router.patch("/disponible", response_model=UsuarioResponse)
async def toggle_disponible(
    datos: ToggleDisponibleRequest,
    usuario: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    await db.usuarios.update_one(
        {"_id": ObjectId(usuario["id"])},
        {"$set": {"horario_trabajo.disponible_manual": datos.disponible_manual}},
    )
    doc = await db.usuarios.find_one({"_id": ObjectId(usuario["id"])}, {"password_hash": 0})
    return _doc_a_response(doc)


@router.get("/buscar", response_model=list[UsuarioResponse])
async def buscar_usuarios(
    q: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    docs = await db.usuarios.find(
        {
            "$or": [
                {"email": {"$regex": q, "$options": "i"}},
                {"telefono": {"$regex": q, "$options": "i"}},
                {"nombre": {"$regex": q, "$options": "i"}},
            ],
            "_id": {"$ne": ObjectId(usuario["id"])},
        },
        {"password_hash": 0},
    ).to_list(length=10)
    return [_doc_a_response(d) for d in docs]


@router.get("/{usuario_id}/disponible")
async def obtener_disponibilidad(
    usuario_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    try:
        doc = await db.usuarios.find_one({"_id": ObjectId(usuario_id)}, {"password_hash": 0})
    except Exception:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not doc:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    horario_raw = doc.get("horario_trabajo")
    horario = HorarioTrabajo(**horario_raw) if horario_raw else None
    return {
        "disponible": _esta_disponible(doc),
        "horario_trabajo": horario,
        "nombre": doc["nombre"],
    }


@router.delete("/perfil", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_cuenta(
    usuario: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    uid = usuario["id"]
    await db.usuarios.delete_one({"_id": ObjectId(uid)})
    await db.sesiones.delete_many({"usuario_id": uid})
