from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..database import get_db
from ..models.usuario import EnviarCodigoRequest, RegistroRequest, LoginRequest, TokenResponse
from ..services import auth_service
from ..services.email_service import generar_y_guardar_codigo, enviar_codigo_verificacion

router = APIRouter()
_bearer = HTTPBearer()


@router.post("/enviar-codigo", status_code=status.HTTP_200_OK)
async def enviar_codigo(datos: EnviarCodigoRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    # Validar disponibilidad antes de gastar el envío
    await auth_service.verificar_disponibilidad(db, datos.email, datos.telefono)
    codigo = await generar_y_guardar_codigo(db, datos.email)
    await enviar_codigo_verificacion(datos.email, codigo)
    return {"mensaje": "Código enviado a tu correo"}


@router.post("/registro", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def registro(datos: RegistroRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await auth_service.registrar_usuario(db, datos)


@router.post("/login", response_model=TokenResponse)
async def login(datos: LoginRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await auth_service.login_usuario(db, datos)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    credenciales: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    await auth_service.logout_usuario(db, credenciales.credentials)
    return {"mensaje": "Sesión cerrada"}
