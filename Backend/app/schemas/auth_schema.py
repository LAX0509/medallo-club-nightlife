from pydantic import BaseModel, EmailStr, Field, field_validator

from app.domain.enums import RolUsuario


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegistroPromotorRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    telefono: str | None = Field(default=None, max_length=20)

    @field_validator("password")
    @classmethod
    def password_debe_tener_numero(cls, value: str) -> str:
        if not any(char.isdigit() for char in value):
            raise ValueError("La contraseña debe contener al menos un número")
        return value


class RegistroPromotorRespuesta(BaseModel):
    nombre: str
    email: EmailStr
    mensaje: str


class TokenRespuesta(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: RolUsuario
    usuario_id: int
    nombre: str
