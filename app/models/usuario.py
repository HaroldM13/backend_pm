from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class EnviarCodigoRequest(BaseModel):
    email: EmailStr
    telefono: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")


class RegistroRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    email: EmailStr
    telefono: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    password: str = Field(min_length=8)
    confirmar_password: str
    codigo: str = Field(min_length=6, max_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ActualizarPerfilRequest(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)


class UsuarioResponse(BaseModel):
    id: str
    nombre: str
    email: str
    telefono: str
    avatar_url: Optional[str] = None
    created_at: str


class TokenResponse(BaseModel):
    token: str
    usuario: UsuarioResponse
