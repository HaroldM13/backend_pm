from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from bson import ObjectId
import uuid
import os
import shutil
import json

from ..database import get_db
from ..dependencies import get_current_user
from ..utils.helpers import fecha_a_str
from ..models.evidencia import EvidenciaResponse

router = APIRouter()
UPLOAD_DIR = "uploads/evidencias"


def _evidencia_a_response(doc: dict) -> EvidenciaResponse:
    return EvidenciaResponse(
        id=str(doc["_id"]),
        tarea_id=doc["tarea_id"],
        usuario_id=doc["usuario_id"],
        nombre_usuario=doc.get("nombre_usuario", ""),
        urls=doc.get("urls", []),
        nombres=doc.get("nombres", []),
        tipos=doc.get("tipos", []),
        comentario=doc.get("comentario", ""),
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


def _guardar_archivo(archivo: UploadFile) -> tuple[str, str, str]:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(archivo.filename or "")[1].lower() or ".bin"
    nombre_unico = f"{uuid.uuid4().hex}{ext}"
    ruta = os.path.join(UPLOAD_DIR, nombre_unico)
    with open(ruta, "wb") as f:
        shutil.copyfileobj(archivo.file, f)
    url = f"/uploads/evidencias/{nombre_unico}"
    return url, archivo.filename or nombre_unico, archivo.content_type or "application/octet-stream"


@router.get("/tarea/{tarea_id}", response_model=list[EvidenciaResponse])
async def listar_evidencias(
    tarea_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    await _verificar_acceso_tarea(db, tarea_id, usuario["id"])
    docs = await db.evidencias.find({"tarea_id": tarea_id}).sort("created_at", 1).to_list(100)
    return [_evidencia_a_response(d) for d in docs]


@router.post("/tarea/{tarea_id}", response_model=EvidenciaResponse, status_code=status.HTTP_201_CREATED)
async def crear_evidencia(
    tarea_id: str,
    comentario: str = Form(default=""),
    archivos: list[UploadFile] = File(default=[]),
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    await _verificar_acceso_tarea(db, tarea_id, usuario["id"])

    urls, nombres, tipos = [], [], []
    for archivo in archivos:
        if archivo.filename:
            u, n, t = _guardar_archivo(archivo)
            urls.append(u)
            nombres.append(n)
            tipos.append(t)

    ahora = datetime.now(timezone.utc)
    doc = {
        "tarea_id": tarea_id,
        "usuario_id": usuario["id"],
        "nombre_usuario": usuario.get("nombre", ""),
        "urls": urls,
        "nombres": nombres,
        "tipos": tipos,
        "comentario": comentario,
        "created_at": ahora,
    }
    resultado = await db.evidencias.insert_one(doc)
    doc["_id"] = resultado.inserted_id
    return _evidencia_a_response(doc)


@router.patch("/{evidencia_id}", response_model=EvidenciaResponse)
async def actualizar_evidencia(
    evidencia_id: str,
    comentario: str = Form(default=""),
    nuevos_archivos: list[UploadFile] = File(default=[]),
    indices_eliminar: str = Form(default="[]"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    try:
        doc = await db.evidencias.find_one({"_id": ObjectId(evidencia_id)})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidencia no encontrada")

    if doc["usuario_id"] != usuario["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el creador puede editar")

    try:
        indices_list: list[int] = json.loads(indices_eliminar)
    except Exception:
        indices_list = []

    urls = list(doc.get("urls", []))
    nombres = list(doc.get("nombres", []))
    tipos = list(doc.get("tipos", []))

    # Eliminar por índice en orden descendente para no desplazar índices
    for idx in sorted(set(indices_list), reverse=True):
        if 0 <= idx < len(urls):
            ruta_fisica = "." + urls[idx]
            if os.path.exists(ruta_fisica):
                os.remove(ruta_fisica)
            urls.pop(idx)
            if idx < len(nombres):
                nombres.pop(idx)
            if idx < len(tipos):
                tipos.pop(idx)

    for archivo in nuevos_archivos:
        if archivo.filename:
            u, n, t = _guardar_archivo(archivo)
            urls.append(u)
            nombres.append(n)
            tipos.append(t)

    cambios = {"urls": urls, "nombres": nombres, "tipos": tipos, "comentario": comentario}
    await db.evidencias.update_one({"_id": ObjectId(evidencia_id)}, {"$set": cambios})
    doc.update(cambios)
    return _evidencia_a_response(doc)


@router.delete("/{evidencia_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_evidencia(
    evidencia_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    try:
        doc = await db.evidencias.find_one({"_id": ObjectId(evidencia_id)})
    except Exception:
        doc = None
    if not doc:
        return

    if doc["usuario_id"] != usuario["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el creador puede eliminar")

    for url in doc.get("urls", []):
        ruta_fisica = "." + url
        if os.path.exists(ruta_fisica):
            os.remove(ruta_fisica)

    await db.evidencias.delete_one({"_id": ObjectId(evidencia_id)})
