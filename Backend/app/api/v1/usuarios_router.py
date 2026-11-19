from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import get_current_user, get_usuario_service, require_roles
from app.application.usuario_service import UsuarioService
from app.domain.entities.usuario import Usuario
from app.domain.enums import RolUsuario
from app.schemas.usuario_schema import (
    UsuarioActualizar,
    UsuarioCrear,
    UsuarioListaRespuesta,
    UsuarioRespuesta,
)

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.post(
    "",
    response_model=UsuarioRespuesta,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def crear_usuario(
    payload: UsuarioCrear, usuario_service: UsuarioService = Depends(get_usuario_service)
) -> UsuarioRespuesta:
    usuario = usuario_service.registrar(
        nombre=payload.nombre,
        email=payload.email,
        password=payload.password,
        rol=payload.rol,
        telefono=payload.telefono,
    )
    return UsuarioRespuesta.model_validate(usuario)


@router.get(
    "",
    response_model=UsuarioListaRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def listar_usuarios(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    rol: RolUsuario | None = None,
    usuario_service: UsuarioService = Depends(get_usuario_service),
) -> UsuarioListaRespuesta:
    usuarios, total = usuario_service.listar(page=page, limit=limit, rol=rol)
    return UsuarioListaRespuesta(
        items=[UsuarioRespuesta.model_validate(u) for u in usuarios],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/me", response_model=UsuarioRespuesta)
def obtener_usuario_actual(usuario: Usuario = Depends(get_current_user)) -> UsuarioRespuesta:
    return UsuarioRespuesta.model_validate(usuario)


@router.put(
    "/{usuario_id}",
    response_model=UsuarioRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def actualizar_usuario(
    usuario_id: int,
    payload: UsuarioActualizar,
    usuario_service: UsuarioService = Depends(get_usuario_service),
) -> UsuarioRespuesta:
    usuario = usuario_service.actualizar(
        usuario_id,
        nombre=payload.nombre,
        rol=payload.rol,
        estado=payload.estado,
        telefono=payload.telefono,
    )
    return UsuarioRespuesta.model_validate(usuario)
