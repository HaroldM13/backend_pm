from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException, status
from bson import ObjectId
from ..models.proyecto import CrearProyectoRequest, ActualizarProyectoRequest, ProyectoResponse, ColumnaCustom, GestionarColumnasRequest
from ..utils.helpers import fecha_a_str


def _proyecto_a_response(doc: dict) -> ProyectoResponse:
    raw_columnas = doc.get("columnas_custom", [])
    columnas_custom = [
        ColumnaCustom(id=c["id"], nombre=c["nombre"], orden=c.get("orden", 10), color=c.get("color", "indigo"))
        for c in raw_columnas
        if isinstance(c, dict) and c.get("id") and c.get("nombre")
    ]
    return ProyectoResponse(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
        descripcion=doc.get("descripcion"),
        area_id=doc["area_id"],
        creador_id=doc["creador_id"],
        miembros=doc.get("miembros", []),
        chat_grupo_id=doc.get("chat_grupo_id"),
        sprint_activo_id=doc.get("sprint_activo_id"),
        columnas_custom=columnas_custom,
        created_at=fecha_a_str(doc["created_at"]),
    )


async def crear_proyecto(db: AsyncIOMotorDatabase, datos: CrearProyectoRequest, usuario_id: str) -> ProyectoResponse:
    # Verificar que el área existe y el usuario es miembro
    try:
        area_oid = ObjectId(datos.area_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada")

    area = await db.areas.find_one({"_id": area_oid, "miembros": usuario_id})
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada o sin acceso")

    ahora = datetime.now(timezone.utc)
    doc = {
        "nombre": datos.nombre,
        "descripcion": datos.descripcion,
        "area_id": datos.area_id,
        "creador_id": usuario_id,
        "miembros": [usuario_id],
        "chat_grupo_id": None,
        "sprint_activo_id": None,
        "created_at": ahora,
    }
    resultado = await db.proyectos.insert_one(doc)
    proyecto_id = str(resultado.inserted_id)

    # Canal de chat propio del proyecto creado automáticamente
    doc_sala = {
        "nombre": datos.nombre,
        "tipo": "proyecto",
        "referencia_id": proyecto_id,
        "miembros": [usuario_id],
        "created_at": ahora,
    }
    resultado_sala = await db.salas_chat.insert_one(doc_sala)
    sala_id = str(resultado_sala.inserted_id)

    await db.proyectos.update_one({"_id": resultado.inserted_id}, {"$set": {"chat_grupo_id": sala_id}})
    doc["_id"] = resultado.inserted_id
    doc["chat_grupo_id"] = sala_id

    await db.mensajes.insert_one({
        "sala_id": sala_id,
        "remitente_id": "sistema",
        "nombre_remitente": "Sistema",
        "contenido": f"📁 Proyecto **{datos.nombre}** creado. Este es su canal de comunicación.",
        "subtipo": "texto",
        "menciones": [],
        "created_at": ahora,
    })

    return _proyecto_a_response(doc)


async def listar_proyectos(db: AsyncIOMotorDatabase, usuario_id: str, area_id: str | None = None) -> list[ProyectoResponse]:
    filtro: dict = {"miembros": usuario_id}
    if area_id:
        filtro["area_id"] = area_id

    cursor = db.proyectos.find(filtro).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    return [_proyecto_a_response(d) for d in docs]


async def obtener_proyecto(db: AsyncIOMotorDatabase, proyecto_id: str, usuario_id: str) -> ProyectoResponse:
    try:
        oid = ObjectId(proyecto_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    doc = await db.proyectos.find_one({"_id": oid, "miembros": usuario_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    return _proyecto_a_response(doc)


async def actualizar_proyecto(
    db: AsyncIOMotorDatabase, proyecto_id: str, datos: ActualizarProyectoRequest, usuario_id: str
) -> ProyectoResponse:
    try:
        oid = ObjectId(proyecto_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    doc = await db.proyectos.find_one({"_id": oid, "creador_id": usuario_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso para editar este proyecto")

    cambios = {k: v for k, v in datos.model_dump().items() if v is not None}
    if cambios:
        await db.proyectos.update_one({"_id": oid}, {"$set": cambios})
        doc.update(cambios)

    return _proyecto_a_response(doc)


async def eliminar_proyecto(db: AsyncIOMotorDatabase, proyecto_id: str, usuario_id: str) -> None:
    try:
        oid = ObjectId(proyecto_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    doc = await db.proyectos.find_one({"_id": oid, "creador_id": usuario_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso para eliminar este proyecto")

    await db.proyectos.delete_one({"_id": oid})


async def gestionar_columnas(
    db: AsyncIOMotorDatabase, proyecto_id: str, datos: GestionarColumnasRequest, usuario_id: str
) -> ProyectoResponse:
    try:
        oid = ObjectId(proyecto_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    doc = await db.proyectos.find_one({"_id": oid, "miembros": usuario_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    columnas_dict = [c.model_dump() for c in datos.columnas]
    await db.proyectos.update_one({"_id": oid}, {"$set": {"columnas_custom": columnas_dict}})
    doc["columnas_custom"] = columnas_dict
    return _proyecto_a_response(doc)


async def agregar_miembro(
    db: AsyncIOMotorDatabase, proyecto_id: str, email: str | None, telefono: str | None, usuario_id: str
) -> ProyectoResponse:
    try:
        oid = ObjectId(proyecto_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    doc = await db.proyectos.find_one({"_id": oid, "miembros": usuario_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    if not email and not telefono:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provee email o teléfono")

    filtro = {"email": email} if email else {"telefono": telefono}
    nuevo = await db.usuarios.find_one(filtro)
    if not nuevo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    nuevo_id = str(nuevo["_id"])
    if nuevo_id in doc["miembros"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El usuario ya es miembro")

    await db.proyectos.update_one({"_id": oid}, {"$push": {"miembros": nuevo_id}})

    # Agregar al canal de chat del proyecto
    if doc.get("chat_grupo_id"):
        try:
            await db.salas_chat.update_one(
                {"_id": ObjectId(doc["chat_grupo_id"])},
                {"$push": {"miembros": nuevo_id}},
            )
        except Exception:
            pass

    # Auto-agregar al área y su canal si el usuario aún no es miembro
    try:
        area = await db.areas.find_one({"_id": ObjectId(doc["area_id"])})
        if area and nuevo_id not in area.get("miembros", []):
            await db.areas.update_one(
                {"_id": ObjectId(doc["area_id"])},
                {"$push": {"miembros": nuevo_id}},
            )
            if area.get("chat_grupo_id"):
                await db.salas_chat.update_one(
                    {"_id": ObjectId(area["chat_grupo_id"])},
                    {"$push": {"miembros": nuevo_id}},
                )
    except Exception:
        pass  # No bloquear si el área falla — el proyecto ya fue actualizado

    doc["miembros"].append(nuevo_id)
    return _proyecto_a_response(doc)
