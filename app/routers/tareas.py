from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from bson import ObjectId
from ..database import get_db
from ..dependencies import get_current_user
from ..models.tarea import (
    CrearTareaRequest, ActualizarTareaRequest, RegistrarHorasRequest,
    TareaResponse, HoraLogResponse, ActividadMensualResponse,
    EntradaHoraActividad, TareaCompletadaActividad, SprintActividad,
)
from ..utils.helpers import fecha_a_str
from ..websocket.manager import manager
import json

router = APIRouter()


def _tarea_a_response(doc: dict) -> TareaResponse:
    return TareaResponse(
        id=str(doc["_id"]),
        titulo=doc["titulo"],
        descripcion=doc.get("descripcion"),
        proyecto_id=doc["proyecto_id"],
        epica_id=doc.get("epica_id"),
        sprint_id=doc.get("sprint_id"),
        columna=doc["columna"],
        asignado_a=doc.get("asignado_a"),
        creado_por=doc["creado_por"],
        prioridad=doc["prioridad"],
        horas_estimadas=doc.get("horas_estimadas", 0),
        horas_registradas=doc.get("horas_registradas", 0),
        fecha_inicio=doc.get("fecha_inicio"),
        fecha_vencimiento=doc.get("fecha_vencimiento"),
        etiquetas=doc.get("etiquetas", []),
        completada_en=doc.get("completada_en"),
        created_at=fecha_a_str(doc["created_at"]),
        tipo_tarea=doc.get("tipo_tarea", "tarea"),
        puntos_historia=doc.get("puntos_historia", 0),
        criterios_aceptacion=doc.get("criterios_aceptacion"),
    )


async def _notificar_chat(db: AsyncIOMotorDatabase, proyecto_id: str, contenido: str) -> None:
    # Enviar mensaje automático al canal del proyecto
    proyecto = await db.proyectos.find_one({"_id": ObjectId(proyecto_id)})
    if not proyecto or not proyecto.get("chat_grupo_id"):
        return

    sala_id = proyecto["chat_grupo_id"]
    ahora = datetime.now(timezone.utc)
    doc_msg = {
        "sala_id": sala_id,
        "remitente_id": "sistema",
        "nombre_remitente": "Sistema",
        "contenido": contenido,
        "subtipo": "texto",
        "menciones": [],
        "created_at": ahora,
    }
    resultado = await db.mensajes.insert_one(doc_msg)

    # Broadcast a clientes WS conectados
    await manager.broadcast(sala_id, {
        "id": str(resultado.inserted_id),
        "sala_id": sala_id,
        "remitente_id": "sistema",
        "nombre_remitente": "Sistema",
        "contenido": contenido,
        "subtipo": "texto",
        "menciones": [],
        "created_at": fecha_a_str(ahora),
    })


@router.get("/proyecto/{proyecto_id}", response_model=list[TareaResponse])
async def listar_tareas(
    proyecto_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    # Solo miembros del proyecto pueden ver las tareas
    proyecto = await db.proyectos.find_one({"_id": ObjectId(proyecto_id), "miembros": usuario["id"]})
    if not proyecto:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    docs = await db.tareas.find({"proyecto_id": proyecto_id}).sort("created_at", 1).to_list(length=500)
    return [_tarea_a_response(d) for d in docs]


@router.get("/{tarea_id}", response_model=TareaResponse)
async def obtener_tarea(
    tarea_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    from fastapi import HTTPException
    try:
        doc = await db.tareas.find_one({"_id": ObjectId(tarea_id)})
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada")
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada")
    # Verificar que el usuario sea miembro del proyecto
    proyecto = await db.proyectos.find_one({"_id": ObjectId(doc["proyecto_id"]), "miembros": usuario["id"]})
    if not proyecto:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso")
    return _tarea_a_response(doc)


@router.post("/", response_model=TareaResponse, status_code=status.HTTP_201_CREATED)
async def crear_tarea(
    datos: CrearTareaRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    proyecto = await db.proyectos.find_one({"_id": ObjectId(datos.proyecto_id), "miembros": usuario["id"]})
    if not proyecto:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    ahora = datetime.now(timezone.utc)
    doc = {
        "titulo": datos.titulo,
        "descripcion": datos.descripcion,
        "proyecto_id": datos.proyecto_id,
        "epica_id": datos.epica_id,
        "sprint_id": datos.sprint_id,
        "columna": datos.columna,
        "asignado_a": datos.asignado_a,
        "creado_por": usuario["id"],
        "prioridad": datos.prioridad,
        "horas_estimadas": datos.horas_estimadas,
        "horas_registradas": 0.0,
        "fecha_inicio": datos.fecha_inicio,
        "fecha_vencimiento": datos.fecha_vencimiento,
        "etiquetas": datos.etiquetas,
        "created_at": ahora,
    }
    resultado = await db.tareas.insert_one(doc)
    doc["_id"] = resultado.inserted_id

    # Notificar al canal si hay alguien asignado
    if datos.asignado_a:
        asignado = await db.usuarios.find_one({"_id": ObjectId(datos.asignado_a)})
        nombre = asignado["nombre"] if asignado else "alguien"
        await _notificar_chat(db, datos.proyecto_id, f"📌 {usuario['nombre']} asignó **{datos.titulo}** a {nombre}")

    return _tarea_a_response(doc)


@router.patch("/{tarea_id}", response_model=TareaResponse)
async def actualizar_tarea(
    tarea_id: str,
    datos: ActualizarTareaRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    doc = await db.tareas.find_one({"_id": ObjectId(tarea_id)})
    if not doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada")

    # Verificar membresía en el proyecto
    proyecto = await db.proyectos.find_one({"_id": ObjectId(doc["proyecto_id"]), "miembros": usuario["id"]})
    if not proyecto:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")

    columna_anterior = doc["columna"]
    cambios = {k: v for k, v in datos.model_dump().items() if v is not None}

    # Registrar cuándo se completó la tarea
    if datos.columna == "done" and columna_anterior != "done":
        cambios["completada_en"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    elif datos.columna and datos.columna != "done" and columna_anterior == "done":
        # Si se mueve de vuelta desde done, limpiar el campo
        cambios["completada_en"] = None

    if cambios:
        await db.tareas.update_one({"_id": ObjectId(tarea_id)}, {"$set": cambios})
        doc.update(cambios)

    # Notificar cambio de columna al canal del proyecto
    if datos.columna and datos.columna != columna_anterior:
        nombres_base = {
            "backlog": "Backlog", "todo": "Por hacer", "in_progress": "En progreso",
            "review": "En revisión", "done": "Completada",
        }
        nueva = nombres_base.get(datos.columna, datos.columna)
        emoji = "✅" if datos.columna == "done" else "🔄"
        await _notificar_chat(db, doc["proyecto_id"], f"{emoji} {usuario['nombre']} movió **{doc['titulo']}** → {nueva}")

    return _tarea_a_response(doc)


@router.delete("/{tarea_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_tarea(
    tarea_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    doc = await db.tareas.find_one({"_id": ObjectId(tarea_id)})
    if not doc:
        return

    proyecto = await db.proyectos.find_one({"_id": ObjectId(doc["proyecto_id"]), "miembros": usuario["id"]})
    if not proyecto:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")

    await db.tareas.delete_one({"_id": ObjectId(tarea_id)})
    await db.horas_log.delete_many({"tarea_id": tarea_id})


@router.get("/proyecto/{proyecto_id}/actividad", response_model=ActividadMensualResponse)
async def actividad_mensual(
    proyecto_id: str,
    anio: int,
    mes: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    from fastapi import HTTPException
    proyecto = await db.proyectos.find_one({"_id": ObjectId(proyecto_id), "miembros": usuario["id"]})
    if not proyecto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    prefijo_mes = f"{anio:04d}-{mes:02d}"

    # IDs de todas las tareas del proyecto
    tareas_docs = await db.tareas.find({"proyecto_id": proyecto_id}, {"_id": 1, "titulo": 1, "asignado_a": 1, "completada_en": 1}).to_list(length=500)
    tarea_ids = [str(t["_id"]) for t in tareas_docs]
    tarea_map = {str(t["_id"]): t for t in tareas_docs}

    # Horas registradas este mes
    horas_docs = await db.horas_log.find({
        "tarea_id": {"$in": tarea_ids},
        "fecha": {"$regex": f"^{prefijo_mes}"},
    }).to_list(length=2000)

    entradas_horas = [
        EntradaHoraActividad(
            fecha=d["fecha"],
            usuario_id=d["usuario_id"],
            horas=d["horas"],
            tarea_id=d["tarea_id"],
            tarea_titulo=tarea_map.get(d["tarea_id"], {}).get("titulo", ""),
            descripcion=d.get("descripcion", ""),
        )
        for d in horas_docs
    ]

    # Tareas completadas este mes
    completadas_docs = [
        t for t in tareas_docs
        if (t.get("completada_en") or "").startswith(prefijo_mes) and t.get("asignado_a")
    ]
    entradas_completadas = [
        TareaCompletadaActividad(
            fecha=t["completada_en"],
            usuario_id=t["asignado_a"],
            tarea_id=str(t["_id"]),
            titulo=t["titulo"],
        )
        for t in completadas_docs
    ]

    # Sprints del proyecto
    sprints_docs = await db.sprints.find({"proyecto_id": proyecto_id}).to_list(length=50)
    sprints = [
        SprintActividad(
            id=str(s["_id"]),
            nombre=s["nombre"],
            fecha_inicio=s["fecha_inicio"],
            fecha_fin=s["fecha_fin"],
            estado=s["estado"],
        )
        for s in sprints_docs
    ]

    return ActividadMensualResponse(
        horas=entradas_horas,
        completadas=entradas_completadas,
        sprints=sprints,
    )


@router.post("/{tarea_id}/horas", response_model=HoraLogResponse, status_code=status.HTTP_201_CREATED)
async def registrar_horas(
    tarea_id: str,
    datos: RegistrarHorasRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    doc = await db.tareas.find_one({"_id": ObjectId(tarea_id)})
    if not doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada")

    ahora = datetime.now(timezone.utc)
    log = {
        "tarea_id": tarea_id,
        "usuario_id": usuario["id"],
        "horas": datos.horas,
        "descripcion": datos.descripcion,
        "fecha": datos.fecha,
        "created_at": ahora,
    }
    resultado = await db.horas_log.insert_one(log)

    # Sumar horas al total de la tarea
    await db.tareas.update_one({"_id": ObjectId(tarea_id)}, {"$inc": {"horas_registradas": datos.horas}})

    return HoraLogResponse(
        id=str(resultado.inserted_id),
        tarea_id=tarea_id,
        usuario_id=usuario["id"],
        horas=datos.horas,
        descripcion=datos.descripcion,
        fecha=datos.fecha,
        created_at=fecha_a_str(ahora),
    )


@router.get("/{tarea_id}/horas", response_model=list[HoraLogResponse])
async def listar_horas(
    tarea_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    docs = await db.horas_log.find({"tarea_id": tarea_id}).sort("fecha", -1).to_list(length=200)
    return [
        HoraLogResponse(
            id=str(d["_id"]),
            tarea_id=d["tarea_id"],
            usuario_id=d["usuario_id"],
            horas=d["horas"],
            descripcion=d["descripcion"],
            fecha=d["fecha"],
            created_at=fecha_a_str(d["created_at"]),
        )
        for d in docs
    ]
