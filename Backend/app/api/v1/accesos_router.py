from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_acceso_service, get_current_user, get_db, require_roles
from app.application import notificacion_service
from app.application.acceso_service import AccesoService, ResultadoRegistroAcceso
from app.domain.entities.usuario import Usuario
from app.domain.enums import NivelAlerta, ResultadoAcceso, RolUsuario, TipoAcceso
from app.infrastructure.models.acceso_qr_model import AccesoQRModel
from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.incidencia_puerta_model import IncidenciaPuertaModel
from app.schemas.acceso_qr_schema import (
    AccesoQRCrear,
    AccesoQRListaRespuesta,
    AccesoQRRegistradoRespuesta,
    AccesoQRRespuesta,
    IncidenciaPuertaCrear,
    IncidenciaPuertaRespuesta,
    ResumenPuertaRespuesta,
)
from app.schemas.alerta_riesgo_schema import AlertaRiesgoRespuesta

router = APIRouter(prefix="/accesos", tags=["Control de accesos QR"])


def _a_respuesta(resultado: ResultadoRegistroAcceso) -> AccesoQRRegistradoRespuesta:
    return AccesoQRRegistradoRespuesta(
        acceso=AccesoQRRespuesta.model_validate(resultado.acceso),
        aforo_actual=resultado.aforo_actual,
        aforo_maximo=resultado.aforo_maximo,
        porcentaje_aforo=resultado.porcentaje_aforo,
        alertas_generadas=[
            AlertaRiesgoRespuesta.model_validate(a) for a in resultado.alertas_generadas
        ],
    )


@router.get(
    "",
    response_model=AccesoQRListaRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.PUERTA, RolUsuario.ADMINISTRADOR))],
)
def listar_accesos(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    evento_id: int | None = None,
    acceso_service: AccesoService = Depends(get_acceso_service),
) -> AccesoQRListaRespuesta:
    accesos, total = acceso_service.listar(page=page, limit=limit, evento_id=evento_id)
    return AccesoQRListaRespuesta(
        items=[AccesoQRRespuesta.model_validate(a) for a in accesos],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/resumen",
    response_model=ResumenPuertaRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.PUERTA, RolUsuario.ADMINISTRADOR))],
)
def resumen_puerta(
    evento_id: int = Query(gt=0), db: Session = Depends(get_db)
) -> ResumenPuertaRespuesta:
    evento = db.get(EventoModel, evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    def contar(resultado: ResultadoAcceso) -> int:
        stmt = select(func.count()).select_from(AccesoQRModel).where(
            AccesoQRModel.evento_id == evento_id,
            AccesoQRModel.resultado == resultado.value,
        )
        return db.execute(stmt).scalar_one()

    validos = contar(ResultadoAcceso.VALIDO)
    return ResumenPuertaRespuesta(
        evento_id=evento.id,
        evento_nombre=evento.nombre,
        aforo_maximo=evento.aforo_maximo,
        accesos_validos=validos,
        accesos_duplicados=contar(ResultadoAcceso.DUPLICADO),
        accesos_rechazados=contar(ResultadoAcceso.RECHAZADO),
        porcentaje_aforo=validos / evento.aforo_maximo if evento.aforo_maximo else 0,
    )


@router.get(
    "/incidencias",
    response_model=list[IncidenciaPuertaRespuesta],
    dependencies=[Depends(require_roles(RolUsuario.PUERTA, RolUsuario.ADMINISTRADOR))],
)
def listar_incidencias_puerta(
    evento_id: int = Query(gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[IncidenciaPuertaRespuesta]:
    stmt = (
        select(IncidenciaPuertaModel)
        .where(IncidenciaPuertaModel.evento_id == evento_id)
        .order_by(IncidenciaPuertaModel.fecha_hora.desc())
        .limit(limit)
    )
    return [
        IncidenciaPuertaRespuesta.model_validate(item)
        for item in db.execute(stmt).scalars().all()
    ]


@router.post(
    "/incidencias",
    response_model=IncidenciaPuertaRespuesta,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RolUsuario.PUERTA, RolUsuario.ADMINISTRADOR))],
)
def crear_incidencia_puerta(
    payload: IncidenciaPuertaCrear,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncidenciaPuertaRespuesta:
    if db.get(EventoModel, payload.evento_id) is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    incidencia = IncidenciaPuertaModel(
        evento_id=payload.evento_id,
        usuario_id=usuario.id,
        tipo=payload.tipo,
        persona=payload.persona.strip() if payload.persona else None,
        descripcion=payload.descripcion.strip(),
    )
    db.add(incidencia)
    db.commit()
    db.refresh(incidencia)
    return IncidenciaPuertaRespuesta.model_validate(incidencia)


@router.get(
    "/{acceso_id}",
    response_model=AccesoQRRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.PUERTA, RolUsuario.ADMINISTRADOR))],
)
def obtener_acceso(
    acceso_id: int, acceso_service: AccesoService = Depends(get_acceso_service)
) -> AccesoQRRespuesta:
    return AccesoQRRespuesta.model_validate(acceso_service.obtener(acceso_id))


@router.post(
    "",
    response_model=AccesoQRRegistradoRespuesta,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RolUsuario.PUERTA, RolUsuario.ADMINISTRADOR))],
)
def registrar_acceso(
    payload: AccesoQRCrear,
    acceso_service: AccesoService = Depends(get_acceso_service),
    db: Session = Depends(get_db),
) -> AccesoQRRegistradoRespuesta:
    if payload.tipo == TipoAcceso.CORTESIA_MANUAL:
        resultado = acceso_service.registrar_cortesia_manual(
            evento_id=payload.evento_id, justificacion=payload.justificacion
        )
    else:
        resultado = acceso_service.registrar_acceso_qr(
            evento_id=payload.evento_id, qr_code=payload.qr_code
        )
    # Las alertas de riesgo alto llegan también a la campana del equipo.
    for alerta in resultado.alertas_generadas:
        if alerta.nivel == NivelAlerta.ALTO:
            notificacion_service.notificar(
                db,
                tipo="alerta_riesgo",
                titulo=f"Riesgo alto: {alerta.tipo_alerta.value.replace('_', ' ')}",
                mensaje=alerta.descripcion,
                nivel="critica",
                enlace="/dashboard",
                # Una sola notificación abierta por evento y tipo de riesgo: evita la
                # "fatiga de alertas" cuando se repite el mismo intento muchas veces.
                referencia=f"alerta:{alerta.tipo_alerta.value}:{alerta.evento_id}",
                deduplicar=True,
            )
    return _a_respuesta(resultado)


@router.put(
    "/{acceso_id}",
    response_model=AccesoQRRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR, RolUsuario.PUERTA))],
)
def anular_acceso(
    acceso_id: int, acceso_service: AccesoService = Depends(get_acceso_service)
) -> AccesoQRRespuesta:
    return AccesoQRRespuesta.model_validate(acceso_service.anular(acceso_id))


@router.delete(
    "/{acceso_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def eliminar_acceso(
    acceso_id: int, acceso_service: AccesoService = Depends(get_acceso_service)
) -> None:
    acceso_service.eliminar(acceso_id)
