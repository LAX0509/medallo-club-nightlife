from fastapi import APIRouter, Depends

from app.api.v1.deps import get_auth_service, get_usuario_service
from app.application.auth_service import AuthService
from app.application.usuario_service import UsuarioService
from app.domain.enums import RolUsuario
from app.schemas.auth_schema import (
    LoginRequest,
    RegistroPromotorRequest,
    RegistroPromotorRespuesta,
    TokenRespuesta,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenRespuesta)
def login(
    payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)
) -> TokenRespuesta:
    usuario, token = auth_service.autenticar(payload.email, payload.password)
    return TokenRespuesta(
        access_token=token,
        rol=usuario.rol,
        usuario_id=usuario.id,
        nombre=usuario.nombre,
    )


@router.post("/register", response_model=RegistroPromotorRespuesta, status_code=201)
def registrar_promotor(
    payload: RegistroPromotorRequest,
    usuario_service: UsuarioService = Depends(get_usuario_service),
) -> RegistroPromotorRespuesta:
    usuario = usuario_service.registrar(
        nombre=payload.nombre.strip(),
        email=str(payload.email).lower(),
        password=payload.password,
        rol=RolUsuario.PROMOTOR,
        telefono=payload.telefono.strip() if payload.telefono else None,
    )
    return RegistroPromotorRespuesta(
        nombre=usuario.nombre,
        email=usuario.email,
        mensaje="Cuenta de promotor creada. Ya puedes iniciar sesión.",
    )
