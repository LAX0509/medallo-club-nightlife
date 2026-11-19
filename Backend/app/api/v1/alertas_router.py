from fastapi import APIRouter, Depends

from app.api.v1.deps import get_alerta_service, require_roles
from app.application.alerta_service import AlertaService
from app.domain.enums import EstadoAlerta, NivelAlerta, RolUsuario
from app.schemas.alerta_riesgo_schema import (
    AlertaRiesgoActualizar,
    AlertaRiesgoListaRespuesta,
    AlertaRiesgoRespuesta,
)

router = APIRouter(
    prefix="/alertas",
    tags=["Motor de riesgos y alertas"],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)


@router.get("", response_model=AlertaRiesgoListaRespuesta)
def listar_alertas(
    evento_id: int | None = None,
    nivel: NivelAlerta | None = None,
    estado: EstadoAlerta | None = None,
    alerta_service: AlertaService = Depends(get_alerta_service),
) -> AlertaRiesgoListaRespuesta:
    alertas = alerta_service.listar(evento_id=evento_id, nivel=nivel, estado=estado)
    return AlertaRiesgoListaRespuesta(
        items=[AlertaRiesgoRespuesta.model_validate(a) for a in alertas], total=len(alertas)
    )


@router.get("/{alerta_id}", response_model=AlertaRiesgoRespuesta)
def obtener_alerta(
    alerta_id: int, alerta_service: AlertaService = Depends(get_alerta_service)
) -> AlertaRiesgoRespuesta:
    return AlertaRiesgoRespuesta.model_validate(alerta_service.obtener(alerta_id))


@router.put("/{alerta_id}", response_model=AlertaRiesgoRespuesta)
def actualizar_alerta(
    alerta_id: int,
    payload: AlertaRiesgoActualizar,
    alerta_service: AlertaService = Depends(get_alerta_service),
) -> AlertaRiesgoRespuesta:
    alerta = alerta_service.actualizar_estado(alerta_id, payload.estado)
    return AlertaRiesgoRespuesta.model_validate(alerta)
