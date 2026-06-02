import io
import uuid
from pathlib import Path
from PIL import Image
from fastapi import UploadFile, HTTPException, status

_UPLOADS_BASE = Path("uploads")
_MAX_DIM = 1200
_JPEG_QUALITY = 75
_MAX_TAMANO_MB = 10


def _directorio_usuario(usuario_id: str) -> Path:
    directorio = _UPLOADS_BASE / "images" / usuario_id
    directorio.mkdir(parents=True, exist_ok=True)
    return directorio


async def guardar_imagen(archivo: UploadFile, usuario_id: str) -> str:
    contenido = await archivo.read()

    if len(contenido) > _MAX_TAMANO_MB * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Imagen demasiado grande (máx 10MB)")

    try:
        imagen = Image.open(io.BytesIO(contenido))
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Archivo no válido como imagen")

    # Convertir a RGB para guardar como JPEG sin errores con RGBA/P
    if imagen.mode not in ("RGB", "L"):
        imagen = imagen.convert("RGB")

    # Reducir si supera el límite sin distorsionar proporción
    if imagen.width > _MAX_DIM or imagen.height > _MAX_DIM:
        imagen.thumbnail((_MAX_DIM, _MAX_DIM), Image.LANCZOS)

    nombre = f"{uuid.uuid4()}.jpg"
    ruta = _directorio_usuario(usuario_id) / nombre
    imagen.save(ruta, format="JPEG", quality=_JPEG_QUALITY, optimize=True)

    return f"/uploads/images/{usuario_id}/{nombre}"


async def guardar_archivo(archivo: UploadFile, usuario_id: str) -> tuple[str, str, int]:
    # Devuelve (url, nombre_original, tamaño_bytes)
    directorio = _UPLOADS_BASE / "archivos" / usuario_id
    directorio.mkdir(parents=True, exist_ok=True)

    contenido = await archivo.read()
    tamano = len(contenido)

    if tamano > _MAX_TAMANO_MB * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Archivo demasiado grande (máx 10MB)")

    extension = Path(archivo.filename or "archivo").suffix
    nombre = f"{uuid.uuid4()}{extension}"
    ruta = directorio / nombre

    ruta.write_bytes(contenido)

    return f"/uploads/archivos/{usuario_id}/{nombre}", archivo.filename or nombre, tamano
