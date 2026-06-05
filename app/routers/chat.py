from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status, UploadFile, File, Form
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from bson import ObjectId
from pydantic import BaseModel
from ..database import get_db
from ..dependencies import get_current_user
from ..models.chat import MensajeResponse, SalaChatResponse, CrearGrupoRequest, CompartirTareaRequest
from ..models.usuario import UsuarioResponse
from ..utils.helpers import fecha_a_str
from ..utils.security import decodificar_token
from ..websocket.manager import manager
from ..services.imagen_service import guardar_imagen, guardar_archivo

router = APIRouter()


class IniciarDirectoRequest(BaseModel):
    destinatario_id: str


def _sala_a_response(doc: dict) -> SalaChatResponse:
    return SalaChatResponse(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
        tipo=doc["tipo"],
        referencia_id=doc.get("referencia_id"),
        miembros=doc.get("miembros", []),
        created_at=fecha_a_str(doc["created_at"]),
    )


def _mensaje_a_response(doc: dict, nombre_remitente: str = "") -> MensajeResponse:
    return MensajeResponse(
        id=str(doc["_id"]),
        sala_id=doc["sala_id"],
        remitente_id=doc["remitente_id"],
        nombre_remitente=doc.get("nombre_remitente", nombre_remitente),
        contenido=doc["contenido"],
        subtipo=doc.get("subtipo", "texto"),
        archivo_url=doc.get("archivo_url"),
        archivo_nombre=doc.get("archivo_nombre"),
        archivo_tamano=doc.get("archivo_tamano"),
        menciones=doc.get("menciones", []),
        reply_to_id=doc.get("reply_to_id"),
        reply_to_preview=doc.get("reply_to_preview"),
        reply_to_remitente=doc.get("reply_to_remitente"),
        tarea_id=doc.get("tarea_id"),
        tarea_titulo=doc.get("tarea_titulo"),
        tarea_columna=doc.get("tarea_columna"),
        tarea_prioridad=doc.get("tarea_prioridad"),
        tarea_proyecto_id=doc.get("tarea_proyecto_id"),
        created_at=fecha_a_str(doc["created_at"]),
    )


# ─── Salas ───────────────────────────────────────────────────────────────────

@router.get("/salas", response_model=list[SalaChatResponse])
async def listar_salas(
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    docs = await db.salas_chat.find({"miembros": usuario["id"]}).sort("created_at", -1).to_list(length=200)
    return [_sala_a_response(d) for d in docs]


@router.get("/salas/{sala_id}/mensajes", response_model=list[MensajeResponse])
async def historial_mensajes(
    sala_id: str,
    antes_de: str | None = None,
    limite: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    sala = await db.salas_chat.find_one({"_id": ObjectId(sala_id), "miembros": usuario["id"]})
    if not sala:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")

    filtro: dict = {"sala_id": sala_id}
    if antes_de:
        try:
            filtro["_id"] = {"$lt": ObjectId(antes_de)}
        except Exception:
            pass

    limite = min(max(limite, 1), 100)
    # Obtener los N más recientes, luego invertir para mostrar cronológicamente
    docs = await db.mensajes.find(filtro).sort("_id", -1).limit(limite).to_list(length=limite)
    return [_mensaje_a_response(d) for d in reversed(docs)]


@router.get("/salas/{sala_id}/miembros", response_model=list[UsuarioResponse])
async def miembros_de_sala(
    sala_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    sala = await db.salas_chat.find_one({"_id": ObjectId(sala_id), "miembros": usuario["id"]})
    if not sala:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")

    miembro_ids = [ObjectId(uid) for uid in sala.get("miembros", []) if uid != usuario["id"]]
    docs = await db.usuarios.find({"_id": {"$in": miembro_ids}}, {"password_hash": 0}).to_list(length=100)

    from ..utils.helpers import fecha_a_str as f
    return [
        UsuarioResponse(
            id=str(d["_id"]),
            nombre=d["nombre"],
            email=d["email"],
            telefono=d["telefono"],
            avatar_url=d.get("avatar_url"),
            created_at=f(d["created_at"]),
        )
        for d in docs
    ]


# ─── Mensajes directos ────────────────────────────────────────────────────────

@router.post("/directo", response_model=SalaChatResponse, status_code=status.HTTP_200_OK)
async def obtener_o_crear_directo(
    datos: IniciarDirectoRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    dest = await db.usuarios.find_one({"_id": ObjectId(datos.destinatario_id)})
    if not dest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    ids = sorted([usuario["id"], datos.destinatario_id])
    sala = await db.salas_chat.find_one({"tipo": "directo", "miembros": {"$all": ids, "$size": 2}})
    if sala:
        return _sala_a_response(sala)

    ahora = datetime.now(timezone.utc)
    doc = {
        "nombre": f"{usuario['nombre']} · {dest['nombre']}",
        "tipo": "directo",
        "miembros": ids,
        "created_at": ahora,
    }
    resultado = await db.salas_chat.insert_one(doc)
    doc["_id"] = resultado.inserted_id
    return _sala_a_response(doc)


# ─── Grupos ───────────────────────────────────────────────────────────────────

@router.post("/grupos", response_model=SalaChatResponse, status_code=status.HTTP_201_CREATED)
async def crear_grupo(
    datos: CrearGrupoRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    # El creador siempre es miembro
    miembros_ids = list(set([usuario["id"]] + datos.miembro_ids))

    # Verificar que los IDs de miembros existen
    for uid in datos.miembro_ids:
        existe = await db.usuarios.find_one({"_id": ObjectId(uid)})
        if not existe:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuario {uid} no encontrado")

    ahora = datetime.now(timezone.utc)
    doc = {
        "nombre": datos.nombre,
        "tipo": "grupo",
        "creador_id": usuario["id"],
        "miembros": miembros_ids,
        "created_at": ahora,
    }
    resultado = await db.salas_chat.insert_one(doc)
    doc["_id"] = resultado.inserted_id
    return _sala_a_response(doc)


# ─── Compartir tarea ──────────────────────────────────────────────────────────

@router.post("/salas/{sala_id}/tarea", response_model=MensajeResponse, status_code=status.HTTP_201_CREATED)
async def compartir_tarea(
    sala_id: str,
    datos: CompartirTareaRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    sala = await db.salas_chat.find_one({"_id": ObjectId(sala_id), "miembros": usuario["id"]})
    if not sala:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")

    # Validar que las menciones son miembros de la sala
    miembros_sala = set(sala.get("miembros", []))
    menciones_validas = [uid for uid in datos.menciones if uid in miembros_sala]

    ahora = datetime.now(timezone.utc)
    doc = {
        "sala_id": sala_id,
        "remitente_id": usuario["id"],
        "nombre_remitente": usuario["nombre"],
        "contenido": datos.comentario or "",
        "subtipo": "tarea",
        "menciones": menciones_validas,
        "tarea_id": datos.tarea_id,
        "tarea_titulo": datos.tarea_titulo,
        "tarea_columna": datos.tarea_columna,
        "tarea_prioridad": datos.tarea_prioridad,
        "tarea_proyecto_id": datos.tarea_proyecto_id,
        "created_at": ahora,
    }
    resultado = await db.mensajes.insert_one(doc)
    doc["_id"] = resultado.inserted_id

    payload = _mensaje_a_response(doc)
    await manager.broadcast(sala_id, payload.model_dump())
    return payload


# ─── Imágenes y archivos ──────────────────────────────────────────────────────

@router.post("/salas/{sala_id}/imagen", response_model=MensajeResponse, status_code=status.HTTP_201_CREATED)
async def enviar_imagen(
    sala_id: str,
    archivo: UploadFile = File(...),
    menciones: str = Form(default="[]"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    sala = await db.salas_chat.find_one({"_id": ObjectId(sala_id), "miembros": usuario["id"]})
    if not sala:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")

    url = await guardar_imagen(archivo, usuario["id"])
    import json
    menciones_lista: list[str] = json.loads(menciones) if menciones else []

    ahora = datetime.now(timezone.utc)
    doc = {
        "sala_id": sala_id,
        "remitente_id": usuario["id"],
        "nombre_remitente": usuario["nombre"],
        "contenido": url,
        "subtipo": "imagen",
        "archivo_url": url,
        "menciones": menciones_lista,
        "created_at": ahora,
    }
    resultado = await db.mensajes.insert_one(doc)
    doc["_id"] = resultado.inserted_id
    payload = _mensaje_a_response(doc)
    await manager.broadcast(sala_id, payload.model_dump())
    return payload


@router.post("/salas/{sala_id}/archivo", response_model=MensajeResponse, status_code=status.HTTP_201_CREATED)
async def enviar_archivo(
    sala_id: str,
    archivo: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    sala = await db.salas_chat.find_one({"_id": ObjectId(sala_id), "miembros": usuario["id"]})
    if not sala:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")

    url, nombre_original, tamano = await guardar_archivo(archivo, usuario["id"])

    ahora = datetime.now(timezone.utc)
    doc = {
        "sala_id": sala_id,
        "remitente_id": usuario["id"],
        "nombre_remitente": usuario["nombre"],
        "contenido": nombre_original,
        "subtipo": "archivo",
        "archivo_url": url,
        "archivo_nombre": nombre_original,
        "archivo_tamano": tamano,
        "menciones": [],
        "created_at": ahora,
    }
    resultado = await db.mensajes.insert_one(doc)
    doc["_id"] = resultado.inserted_id
    payload = _mensaje_a_response(doc)
    await manager.broadcast(sala_id, payload.model_dump())
    return payload


# ─── Alerta de tarea próxima a vencer ────────────────────────────────────────

@router.post("/alerta-tarea/{tarea_id}", status_code=200)
async def alerta_tarea(
    tarea_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    try:
        tarea = await db.tareas.find_one({"_id": ObjectId(tarea_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    proyecto = await db.proyectos.find_one({"_id": ObjectId(tarea["proyecto_id"]), "miembros": usuario["id"]})
    if not proyecto:
        raise HTTPException(status_code=403, detail="Sin acceso")

    prioridad = tarea.get("prioridad", "media")
    vencimiento = tarea.get("fecha_vencimiento", "sin fecha")
    emoji = "🔴" if prioridad == "critica" else "🟠" if prioridad == "alta" else "🟡"
    contenido = (
        f"{emoji} **Alerta de vencimiento**: La tarea **{tarea['titulo']}** vence el {vencimiento}. "
        f"Prioridad: {prioridad}. Por favor, atiéndela a tiempo."
    )

    ahora = datetime.now(timezone.utc)

    # Si tiene asignado → DM con esa persona; si no → canal del proyecto
    asignado_id = tarea.get("asignado_a")
    if asignado_id:
        # Buscar o crear DM
        sala = await db.salas_chat.find_one({
            "tipo": "directo",
            "miembros": {"$all": [usuario["id"], asignado_id], "$size": 2},
        })
        if not sala:
            asignado = await db.usuarios.find_one({"_id": ObjectId(asignado_id)})
            yo = await db.usuarios.find_one({"_id": ObjectId(usuario["id"])})
            nombre_sala = f"{yo['nombre']} · {asignado['nombre']}" if asignado and yo else "DM"
            doc_sala = {
                "nombre": nombre_sala,
                "tipo": "directo",
                "miembros": [usuario["id"], asignado_id],
                "created_at": ahora,
            }
            res_sala = await db.salas_chat.insert_one(doc_sala)
            sala_id = str(res_sala.inserted_id)
        else:
            sala_id = str(sala["_id"])
    else:
        if not proyecto.get("chat_grupo_id"):
            raise HTTPException(status_code=400, detail="El proyecto no tiene canal de chat")
        sala_id = proyecto["chat_grupo_id"]

    doc_msg = {
        "sala_id": sala_id,
        "remitente_id": usuario["id"],
        "nombre_remitente": usuario["nombre"],
        "contenido": contenido,
        "subtipo": "texto",
        "menciones": [asignado_id] if asignado_id else [],
        "created_at": ahora,
    }
    resultado = await db.mensajes.insert_one(doc_msg)
    payload = {
        "id": str(resultado.inserted_id),
        "sala_id": sala_id,
        "remitente_id": usuario["id"],
        "nombre_remitente": usuario["nombre"],
        "contenido": contenido,
        "subtipo": "texto",
        "menciones": [asignado_id] if asignado_id else [],
        "created_at": ahora.isoformat(),
    }
    await manager.broadcast(sala_id, payload)
    return {"ok": True, "sala_id": sala_id, "asignado": bool(asignado_id)}


# ─── Mensajes no leídos ────────────────────────────────────────────────────────

@router.get("/no-leidos")
async def no_leidos(
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    uid = usuario["id"]
    salas = await db.salas_chat.find({"miembros": uid}).to_list(length=200)
    total = 0
    por_sala: dict[str, int] = {}
    for sala in salas:
        sala_id = str(sala["_id"])
        lectura = await db.ultima_lectura.find_one({"usuario_id": uid, "sala_id": sala_id})
        filtro: dict = {"sala_id": sala_id, "remitente_id": {"$ne": uid}}
        if lectura:
            filtro["created_at"] = {"$gt": lectura["timestamp"]}
        count = await db.mensajes.count_documents(filtro)
        if count > 0:
            por_sala[sala_id] = count
            total += count
    return {"total": total, "por_sala": por_sala}


@router.post("/salas/{sala_id}/leer", status_code=200)
async def marcar_leida(
    sala_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    uid = usuario["id"]
    ahora = datetime.now(timezone.utc)
    await db.ultima_lectura.update_one(
        {"usuario_id": uid, "sala_id": sala_id},
        {"$set": {"timestamp": ahora}},
        upsert=True,
    )
    return {"ok": True}


# ─── WebSocket ────────────────────────────────────────────────────────────────

@router.websocket("/ws/{sala_id}")
async def websocket_chat(sala_id: str, token: str, ws: WebSocket, db: AsyncIOMotorDatabase = Depends(get_db)):
    payload = decodificar_token(token)
    if not payload:
        await ws.close(code=4001)
        return

    usuario_id = payload.get("sub")
    sesion = await db.sesiones.find_one({"token": token, "activo": True})
    if not sesion:
        await ws.close(code=4001)
        return

    sala = await db.salas_chat.find_one({"_id": ObjectId(sala_id), "miembros": usuario_id})
    if not sala:
        await ws.close(code=4003)
        return

    usuario = await db.usuarios.find_one({"_id": ObjectId(usuario_id)})
    nombre = usuario["nombre"] if usuario else "Desconocido"

    await manager.conectar(sala_id, ws)
    try:
        while True:
            data = await ws.receive_json()
            contenido = data.get("contenido", "").strip()
            menciones = data.get("menciones", [])
            reply_to_id = data.get("reply_to_id")

            if not contenido:
                continue

            # Validar que las menciones son miembros de la sala
            miembros_sala = set(sala.get("miembros", []))
            menciones_validas = [uid for uid in menciones if uid in miembros_sala]

            # Si hay reply, obtener preview del mensaje original
            reply_preview = None
            reply_remitente = None
            if reply_to_id:
                try:
                    original = await db.mensajes.find_one({"_id": ObjectId(reply_to_id)})
                    if original:
                        reply_preview = (original.get("contenido", "") or "")[:120]
                        reply_remitente = original.get("nombre_remitente", "")
                except Exception:
                    pass

            ahora = datetime.now(timezone.utc)
            doc = {
                "sala_id": sala_id,
                "remitente_id": usuario_id,
                "nombre_remitente": nombre,
                "contenido": contenido,
                "subtipo": "texto",
                "menciones": menciones_validas,
                "reply_to_id": reply_to_id,
                "reply_to_preview": reply_preview,
                "reply_to_remitente": reply_remitente,
                "created_at": ahora,
            }
            resultado = await db.mensajes.insert_one(doc)
            doc["_id"] = resultado.inserted_id

            await manager.broadcast(sala_id, {
                "id": str(resultado.inserted_id),
                "sala_id": sala_id,
                "remitente_id": usuario_id,
                "nombre_remitente": nombre,
                "contenido": contenido,
                "subtipo": "texto",
                "menciones": menciones_validas,
                "reply_to_id": reply_to_id,
                "reply_to_preview": reply_preview,
                "reply_to_remitente": reply_remitente,
                "created_at": fecha_a_str(ahora),
            })

    except WebSocketDisconnect:
        await manager.desconectar(sala_id, ws)
