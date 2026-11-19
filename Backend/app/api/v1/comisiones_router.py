from fastapi import APIRouter, Depends, status

from app.api.v1.deps import get_comision_service, get_current_user, require_roles
from app.application.comision_service import ComisionService
from app.domain.entities.usuario import Usuario
from app.domain.enums import EstadoComision, RolUsuario
from app.schemas.comision_schema import (
    ComisionActualizar,
    ComisionCrear,
    ComisionRespuesta,
)

router = APIRouter(prefix="/comisiones", tags=["Comisiones de promotores"])


@router.post(
    "",
    response_model=ComisionRespuesta,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def crear_comision(
    payload: ComisionCrear, comision_service: ComisionService = Depends(get_comision_service)
) -> ComisionRespuesta:
    comision = comision_service.crear(
        promotor_id=payload.promotor_id,
        evento_id=payload.evento_id,
        porcentaje=payload.porcentaje,
    )
    return ComisionRespuesta.model_validate(comision)


@router.get("", response_model=list[ComisionRespuesta])
def listar_comisiones(
    promotor_id: int | None = None,
    evento_id: int | None = None,
    estado: EstadoComision | None = None,
    usuario: Usuario = Depends(get_current_user),
    comision_service: ComisionService = Depends(get_comision_service),
) -> list[ComisionRespuesta]:
    # Un Promotor sólo puede consultar sus propias comisiones.
    if usuario.rol == RolUsuario.PROMOTOR:
        promotor_id = usuario.id

    comisiones = comision_service.listar(
        promotor_id=promotor_id, evento_id=evento_id, estado=estado
    )
    return [ComisionRespuesta.model_validate(c) for c in comisiones]


@router.put(
    "/{comision_id}",
    response_model=ComisionRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def actualizar_comision(
    comision_id: int,
    payload: ComisionActualizar,
    comision_service: ComisionService = Depends(get_comision_service),
) -> ComisionRespuesta:
    comision, _alerta = comision_service.actualizar(
        comision_id, estado=payload.estado, monto=payload.monto
    )
    return ComisionRespuesta.model_validate(comision)
