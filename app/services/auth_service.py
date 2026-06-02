from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException, status
from bson import ObjectId
from ..models.usuario import RegistroRequest, LoginRequest, UsuarioResponse, TokenResponse
from ..utils.security import hashear_password, verificar_password, crear_token
from ..utils.helpers import fecha_a_str
from .email_service import verificar_codigo, eliminar_codigo


def _usuario_a_response(doc: dict) -> UsuarioResponse:
    return UsuarioResponse(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
        email=doc["email"],
        telefono=doc["telefono"],
        avatar_url=doc.get("avatar_url"),
        created_at=fecha_a_str(doc["created_at"]),
    )


async def verificar_disponibilidad(db: AsyncIOMotorDatabase, email: str, telefono: str) -> None:
    # Chequea los dos campos antes de gastar el envío del código
    if await db.usuarios.find_one({"email": email}):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo ya está registrado")
    if await db.usuarios.find_one({"telefono": telefono}):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El teléfono ya está registrado")


async def registrar_usuario(db: AsyncIOMotorDatabase, datos: RegistroRequest) -> TokenResponse:
    if datos.password != datos.confirmar_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Las contraseñas no coinciden",
        )

    await verificar_disponibilidad(db, datos.email, datos.telefono)

    valido = await verificar_codigo(db, datos.email, datos.codigo)
    if not valido:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Código inválido o expirado",
        )

    ahora = datetime.now(timezone.utc)
    doc = {
        "nombre": datos.nombre,
        "email": datos.email,
        "telefono": datos.telefono,
        "password_hash": hashear_password(datos.password),
        "avatar_url": None,
        "created_at": ahora,
    }

    try:
        resultado = await db.usuarios.insert_one(doc)
    except Exception:
        # El índice único de MongoDB también protege contra condición de carrera
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo o teléfono ya están registrados")

    usuario_id = str(resultado.inserted_id)
    await eliminar_codigo(db, datos.email)

    token = crear_token({"sub": usuario_id})
    await db.sesiones.insert_one({"token": token, "usuario_id": usuario_id, "activo": True, "created_at": ahora})

    doc["_id"] = resultado.inserted_id
    return TokenResponse(token=token, usuario=_usuario_a_response(doc))


async def login_usuario(db: AsyncIOMotorDatabase, datos: LoginRequest) -> TokenResponse:
    usuario = await db.usuarios.find_one({"email": datos.email})
    if not usuario or not verificar_password(datos.password, usuario["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")

    token = crear_token({"sub": str(usuario["_id"])})
    await db.sesiones.insert_one({
        "token": token,
        "usuario_id": str(usuario["_id"]),
        "activo": True,
        "created_at": datetime.now(timezone.utc),
    })

    return TokenResponse(token=token, usuario=_usuario_a_response(usuario))


async def logout_usuario(db: AsyncIOMotorDatabase, token: str) -> None:
    await db.sesiones.update_one({"token": token}, {"$set": {"activo": False}})
