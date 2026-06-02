from fastapi import APIRouter, Depends, status
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..database import get_db
from ..dependencies import get_current_user
from ..models.proyecto import CrearProyectoRequest, ActualizarProyectoRequest, AgregarMiembroProyectoRequest, GestionarColumnasRequest, ProyectoResponse
from ..services import proyecto_service

router = APIRouter()


@router.get("/", response_model=list[ProyectoResponse])
async def listar_proyectos(
    area_id: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await proyecto_service.listar_proyectos(db, usuario["id"], area_id)


@router.post("/", response_model=ProyectoResponse, status_code=status.HTTP_201_CREATED)
async def crear_proyecto(
    datos: CrearProyectoRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await proyecto_service.crear_proyecto(db, datos, usuario["id"])


@router.get("/{proyecto_id}", response_model=ProyectoResponse)
async def obtener_proyecto(
    proyecto_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await proyecto_service.obtener_proyecto(db, proyecto_id, usuario["id"])


@router.patch("/{proyecto_id}", response_model=ProyectoResponse)
async def actualizar_proyecto(
    proyecto_id: str,
    datos: ActualizarProyectoRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await proyecto_service.actualizar_proyecto(db, proyecto_id, datos, usuario["id"])


@router.delete("/{proyecto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_proyecto(
    proyecto_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    await proyecto_service.eliminar_proyecto(db, proyecto_id, usuario["id"])


@router.patch("/{proyecto_id}/columnas", response_model=ProyectoResponse)
async def gestionar_columnas(
    proyecto_id: str,
    datos: GestionarColumnasRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await proyecto_service.gestionar_columnas(db, proyecto_id, datos, usuario["id"])


@router.post("/{proyecto_id}/miembros", response_model=ProyectoResponse)
async def agregar_miembro(
    proyecto_id: str,
    datos: AgregarMiembroProyectoRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await proyecto_service.agregar_miembro(db, proyecto_id, datos.email, datos.telefono, usuario["id"])
