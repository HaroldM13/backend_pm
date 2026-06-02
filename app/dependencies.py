from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from .database import get_db
from .utils.security import decodificar_token
from .utils.helpers import fecha_a_str

_bearer = HTTPBearer()


async def get_current_user(
    credenciales: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    token = credenciales.credentials
    payload = decodificar_token(token)

    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    # Verificar que la sesión no fue invalidada por logout
    sesion = await db.sesiones.find_one({"token": token, "activo": True})
    if not sesion:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inactiva o expirada")

    usuario = await db.usuarios.find_one({"_id": ObjectId(payload["sub"])})
    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")

    return {
        "id": str(usuario["_id"]),
        "nombre": usuario["nombre"],
        "email": usuario["email"],
        "telefono": usuario["telefono"],
        "avatar_url": usuario.get("avatar_url"),
        "created_at": fecha_a_str(usuario["created_at"]),
        "_token": token,
    }
