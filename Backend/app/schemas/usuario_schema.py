from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.enums import RolUsuario
from app.schemas.common import ListaPaginada


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    rol: RolUsuario
    telefono: str | None = Field(default=None, max_length=20)

    @field_validator("password")
    @classmethod
    def password_debe_tener_numero(cls, value: str) -> str:
        if not any(char.isdigit() for char in value):
            raise ValueError("La contraseña debe contener al menos un número")
        return value


class UsuarioActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    rol: RolUsuario | None = None
    estado: bool | None = None
    telefono: str | None = Field(default=None, max_length=20)


class UsuarioRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: str
    rol: RolUsuario
    telefono: str | None
    estado: bool
    fecha_registro: datetime | None


class UsuarioListaRespuesta(ListaPaginada):
    items: list[UsuarioRespuesta]
