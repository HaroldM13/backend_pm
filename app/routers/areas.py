from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..database import get_db
from ..dependencies import get_current_user
from ..models.area import CrearAreaRequest, ActualizarAreaRequest, AgregarMiembroRequest, AreaResponse
from ..services import area_service

router = APIRouter()


@router.get("/", response_model=list[AreaResponse])
async def listar_areas(
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await area_service.listar_areas(db, usuario["id"])


@router.post("/", response_model=AreaResponse, status_code=status.HTTP_201_CREATED)
async def crear_area(
    datos: CrearAreaRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await area_service.crear_area(db, datos, usuario["id"])


@router.get("/{area_id}", response_model=AreaResponse)
async def obtener_area(
    area_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await area_service.obtener_area(db, area_id, usuario["id"])


@router.patch("/{area_id}", response_model=AreaResponse)
async def actualizar_area(
    area_id: str,
    datos: ActualizarAreaRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await area_service.actualizar_area(db, area_id, datos, usuario["id"])


@router.delete("/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_area(
    area_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    await area_service.eliminar_area(db, area_id, usuario["id"])


@router.post("/{area_id}/miembros", response_model=AreaResponse)
async def agregar_miembro(
    area_id: str,
    datos: AgregarMiembroRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await area_service.agregar_miembro(db, area_id, datos.email, datos.telefono, usuario["id"])


@router.delete("/{area_id}/miembros/{miembro_id}", response_model=AreaResponse)
async def remover_miembro(
    area_id: str,
    miembro_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    usuario: dict = Depends(get_current_user),
):
    return await area_service.remover_miembro(db, area_id, miembro_id, usuario["id"])
