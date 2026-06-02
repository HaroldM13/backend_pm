from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from ..database import get_db
from ..dependencies import get_current_user
from ..models.usuario import UsuarioResponse, ActualizarPerfilRequest
from ..utils.helpers import fecha_a_str

router = APIRouter()


def _doc_a_response(doc: dict) -> UsuarioResponse:
    return UsuarioResponse(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
        email=doc["email"],
        telefono=doc["telefono"],
        avatar_url=doc.get("avatar_url"),
        created_at=fecha_a_str(doc["created_at"]),
    )


@router.get("/", response_model=list[UsuarioResponse])
async def listar_usuarios(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    # Excluir password_hash de la proyección
    docs = await db.usuarios.find({}, {"password_hash": 0}).to_list(length=500)
    return [_doc_a_response(d) for d in docs]


@router.get("/perfil", response_model=UsuarioResponse)
async def obtener_perfil(usuario: dict = Depends(get_current_user)):
    return UsuarioResponse(
        id=usuario["id"],
        nombre=usuario["nombre"],
        email=usuario["email"],
        telefono=usuario["telefono"],
        avatar_url=usuario.get("avatar_url"),
        created_at=usuario["created_at"],
    )


@router.patch("/perfil", response_model=UsuarioResponse)
async def actualizar_perfil(
    datos: ActualizarPerfilRequest,
    usuario: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cambios = {k: v for k, v in datos.model_dump().items() if v is not None}
    if cambios:
        await db.usuarios.update_one({"_id": ObjectId(usuario["id"])}, {"$set": cambios})
        usuario.update(cambios)

    return UsuarioResponse(
        id=usuario["id"],
        nombre=usuario["nombre"],
        email=usuario["email"],
        telefono=usuario["telefono"],
        avatar_url=usuario.get("avatar_url"),
        created_at=usuario["created_at"],
    )


@router.get("/buscar", response_model=list[UsuarioResponse])
async def buscar_usuarios(
    q: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    # Busca por email o teléfono, excluyendo al usuario actual
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


@router.delete("/perfil", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_cuenta(
    usuario: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    uid = usuario["id"]
    await db.usuarios.delete_one({"_id": ObjectId(uid)})
    await db.sesiones.delete_many({"usuario_id": uid})
