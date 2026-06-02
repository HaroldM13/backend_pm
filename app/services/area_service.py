from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException, status
from bson import ObjectId
from ..models.area import CrearAreaRequest, ActualizarAreaRequest, AreaResponse
from ..utils.helpers import fecha_a_str


def _area_a_response(doc: dict) -> AreaResponse:
    return AreaResponse(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
        descripcion=doc.get("descripcion"),
        creador_id=doc["creador_id"],
        miembros=doc.get("miembros", []),
        chat_grupo_id=doc.get("chat_grupo_id"),
        created_at=fecha_a_str(doc["created_at"]),
    )


async def crear_area(db: AsyncIOMotorDatabase, datos: CrearAreaRequest, usuario_id: str) -> AreaResponse:
    ahora = datetime.now(timezone.utc)

    doc_area = {
        "nombre": datos.nombre,
        "descripcion": datos.descripcion,
        "creador_id": usuario_id,
        "miembros": [usuario_id],
        "chat_grupo_id": None,
        "created_at": ahora,
    }
    resultado = await db.areas.insert_one(doc_area)
    area_id = str(resultado.inserted_id)

    # Crear grupo de chat automáticamente al crear el área
    doc_sala = {
        "nombre": datos.nombre,
        "tipo": "area",
        "referencia_id": area_id,
        "miembros": [usuario_id],
        "created_at": ahora,
    }
    resultado_sala = await db.salas_chat.insert_one(doc_sala)
    sala_id = str(resultado_sala.inserted_id)

    await db.areas.update_one({"_id": resultado.inserted_id}, {"$set": {"chat_grupo_id": sala_id}})
    doc_area["_id"] = resultado.inserted_id
    doc_area["chat_grupo_id"] = sala_id

    # Mensaje de bienvenida automático en el canal del área
    await db.mensajes.insert_one({
        "sala_id": sala_id,
        "remitente_id": "sistema",
        "nombre_remitente": "Sistema",
        "contenido": f"🏢 Área **{datos.nombre}** creada. Bienvenidos al canal.",
        "subtipo": "texto",
        "menciones": [],
        "created_at": ahora,
    })

    return _area_a_response(doc_area)


async def listar_areas(db: AsyncIOMotorDatabase, usuario_id: str) -> list[AreaResponse]:
    cursor = db.areas.find({"miembros": usuario_id}).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    return [_area_a_response(d) for d in docs]


async def obtener_area(db: AsyncIOMotorDatabase, area_id: str, usuario_id: str) -> AreaResponse:
    try:
        oid = ObjectId(area_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada")

    doc = await db.areas.find_one({"_id": oid, "miembros": usuario_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada")

    return _area_a_response(doc)


async def actualizar_area(
    db: AsyncIOMotorDatabase, area_id: str, datos: ActualizarAreaRequest, usuario_id: str
) -> AreaResponse:
    try:
        oid = ObjectId(area_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada")

    doc = await db.areas.find_one({"_id": oid, "creador_id": usuario_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso para editar esta área")

    cambios = {k: v for k, v in datos.model_dump().items() if v is not None}
    if cambios:
        await db.areas.update_one({"_id": oid}, {"$set": cambios})
        doc.update(cambios)

    return _area_a_response(doc)


async def eliminar_area(db: AsyncIOMotorDatabase, area_id: str, usuario_id: str) -> None:
    try:
        oid = ObjectId(area_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada")

    doc = await db.areas.find_one({"_id": oid, "creador_id": usuario_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso para eliminar esta área")

    await db.areas.delete_one({"_id": oid})


async def agregar_miembro(
    db: AsyncIOMotorDatabase, area_id: str, email: str | None, telefono: str | None, usuario_id: str
) -> AreaResponse:
    try:
        oid = ObjectId(area_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada")

    doc = await db.areas.find_one({"_id": oid, "miembros": usuario_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada")

    if not email and not telefono:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provee email o teléfono")

    filtro = {"email": email} if email else {"telefono": telefono}
    nuevo = await db.usuarios.find_one(filtro)
    if not nuevo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    nuevo_id = str(nuevo["_id"])
    if nuevo_id in doc["miembros"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El usuario ya es miembro")

    await db.areas.update_one({"_id": oid}, {"$push": {"miembros": nuevo_id}})

    # Agregar también al grupo de chat del área
    if doc.get("chat_grupo_id"):
        try:
            await db.salas_chat.update_one(
                {"_id": ObjectId(doc["chat_grupo_id"])},
                {"$push": {"miembros": nuevo_id}},
            )
        except Exception:
            pass

    doc["miembros"].append(nuevo_id)
    return _area_a_response(doc)


async def remover_miembro(
    db: AsyncIOMotorDatabase, area_id: str, miembro_id: str, usuario_id: str
) -> AreaResponse:
    try:
        oid = ObjectId(area_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada")

    doc = await db.areas.find_one({"_id": oid, "creador_id": usuario_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso")

    if miembro_id == usuario_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes removerte a ti mismo siendo creador")

    await db.areas.update_one({"_id": oid}, {"$pull": {"miembros": miembro_id}})
    doc["miembros"] = [m for m in doc["miembros"] if m != miembro_id]
    return _area_a_response(doc)
