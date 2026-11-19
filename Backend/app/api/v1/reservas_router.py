from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_roles
from app.application import reserva_service
from app.application.whatsapp_notification_service import notificar_confirmacion_reserva, notificar_nueva_reserva
from app.core.tareas import lanzar
from app.domain.entities.usuario import Usuario
from app.domain.enums import RolUsuario
from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.invitado_model import InvitadoModel
from app.infrastructure.models.reserva_model import ReservaModel
from app.infrastructure.models.usuario_model import UsuarioModel
from app.schemas.reserva_schema import (
    ConsultaReservaCliente,
    EstadoReserva,
    EventoReservaRespuesta,
    PaseReservaRespuesta,
    ReservaCancelar,
    ReservaClienteRespuesta,
    ReservaCrear,
    ReservaCreadaRespuesta,
    ReservaEstadoActualizar,
    ReservaRespuesta,
)

router = APIRouter(prefix="/reservas", tags=["Reservas de mesas y palcos"])


def _conteos_pases(db: Session, reserva_ids: list[int]) -> dict[int, tuple[int, int]]:
    if not reserva_ids:
        return {}
    filas = db.execute(
        select(
            InvitadoModel.reserva_id,
            func.count(),
            func.sum(case((InvitadoModel.estado == "usado", 1), else_=0)),
        )
        .where(InvitadoModel.reserva_id.in_(reserva_ids))
        .group_by(InvitadoModel.reserva_id)
    ).all()
    return {rid: (int(total), int(usados or 0)) for rid, total, usados in filas}


def _respuesta(
    model: ReservaModel,
    evento_nombre: str,
    promotor_nombre: str | None = None,
    conteo: tuple[int, int] = (0, 0),
) -> ReservaRespuesta:
    return ReservaRespuesta(
        id=model.id,
        evento_id=model.evento_id,
        promotor_id=model.promotor_id,
        promotor_nombre=promotor_nombre,
        evento_nombre=evento_nombre,
        nombre_cliente=model.nombre_cliente,
        telefono=model.telefono,
        tipo=model.tipo,
        asistentes=model.asistentes,
        notas=model.notas,
        estado=model.estado,
        whatsapp_confirmacion_estado=model.whatsapp_confirmacion_estado,
        whatsapp_confirmacion_error=model.whatsapp_confirmacion_error,
        fecha_solicitud=model.fecha_solicitud,
        garantizada=bool(model.codigo_garantia) and model.estado == "confirmada",
        codigo_garantia=model.codigo_garantia,
        garantizada_en=model.garantizada_en,
        hora_limite=model.hora_limite,
        ubicacion_asignada=model.ubicacion_asignada,
        consumo_minimo=model.consumo_minimo,
        pases_total=conteo[0],
        pases_usados=conteo[1],
    )


def _respuestas(db: Session, filas) -> list[ReservaRespuesta]:
    conteos = _conteos_pases(db, [fila[0].id for fila in filas])
    return [
        _respuesta(reserva, nombre_evento, promotor_nombre, conteos.get(reserva.id, (0, 0)))
        for reserva, nombre_evento, promotor_nombre in filas
    ]


def _datos_confirmacion(reserva: ReservaModel, evento: EventoModel) -> dict:
    return {
        "id": reserva.codigo_garantia or reserva.id,
        "nombre_cliente": reserva.nombre_cliente,
        "telefono": reserva.telefono,
        "evento_nombre": evento.nombre,
        "tipo": "Mesa" if reserva.tipo == "mesa" else "Palco",
        "asistentes": reserva.asistentes,
    }


def _enviar_confirmacion(db: Session, reserva: ReservaModel, evento: EventoModel) -> None:
    estado_aviso, error_aviso, message_id = notificar_confirmacion_reserva(_datos_confirmacion(reserva, evento))
    reserva.whatsapp_confirmacion_estado = estado_aviso
    reserva.whatsapp_confirmacion_error = error_aviso
    reserva.whatsapp_confirmacion_message_id = message_id
    db.commit()
    db.refresh(reserva)


@router.get("/eventos", response_model=list[EventoReservaRespuesta])
def listar_eventos_para_reservas(db: Session = Depends(get_db)) -> list[EventoReservaRespuesta]:
    stmt = (
        select(EventoModel)
        .where(EventoModel.estado == "planeado", EventoModel.fecha >= date.today())
        .order_by(EventoModel.fecha.asc())
        .limit(30)
    )
    eventos = db.execute(stmt).scalars().all()
    return [
        EventoReservaRespuesta(
            id=e.id,
            nombre=e.nombre,
            fecha=e.fecha,
            tematica=e.tematica,
            flyer_url=e.flyer_url,
        )
        for e in eventos
    ]


@router.post(
    "",
    response_model=ReservaCreadaRespuesta,
    status_code=status.HTTP_201_CREATED,
)
def crear_solicitud_reserva(
    payload: ReservaCrear,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ReservaCreadaRespuesta:
    creada = reserva_service.crear_solicitud(
        db,
        evento_id=payload.evento_id,
        promotor_id=payload.promotor_id,
        nombre_cliente=payload.nombre_cliente,
        telefono=payload.telefono,
        tipo=payload.tipo.value,
        asistentes=payload.asistentes,
        notas=payload.notas,
    )
    reserva, evento, promotor = creada.reserva, creada.evento, creada.promotor
    lanzar(
        background_tasks,
        notificar_nueva_reserva,
        {
            "id": reserva.id,
            "nombre_cliente": reserva.nombre_cliente,
            "telefono": reserva.telefono,
            "evento_nombre": evento.nombre,
            "tipo": "Mesa" if reserva.tipo == "mesa" else "Palco",
            "asistentes": reserva.asistentes,
            "promotor": promotor.nombre if promotor else "Solicitud directa",
            "notas": reserva.notas or "Sin observaciones",
        },
    )
    return ReservaCreadaRespuesta(
        **_respuesta(reserva, evento.nombre).model_dump(),
        token_cancelacion=creada.token_cancelacion,
    )


@router.get(
    "/mis-referidas",
    response_model=list[ReservaRespuesta],
    dependencies=[Depends(require_roles(RolUsuario.PROMOTOR))],
)
def listar_reservas_referidas(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReservaRespuesta]:
    stmt = (
        select(ReservaModel, EventoModel.nombre, UsuarioModel.nombre)
        .join(EventoModel, ReservaModel.evento_id == EventoModel.id)
        .outerjoin(UsuarioModel, ReservaModel.promotor_id == UsuarioModel.id)
        .where(ReservaModel.promotor_id == usuario.id)
        .order_by(ReservaModel.fecha_solicitud.desc(), ReservaModel.id.desc())
        .limit(200)
    )
    return _respuestas(db, db.execute(stmt).all())


def _reserva_por_token(db: Session, reserva_id: int, token: str) -> ReservaModel:
    reserva = db.get(ReservaModel, reserva_id)
    if reserva is None or not reserva_service.token_valido(reserva, token):
        raise HTTPException(status_code=404, detail="No se encontró una solicitud cancelable.")
    return reserva


@router.post("/{reserva_id}/mi-reserva", response_model=ReservaClienteRespuesta)
def consultar_mi_reserva(
    reserva_id: int,
    payload: ConsultaReservaCliente,
    db: Session = Depends(get_db),
) -> ReservaClienteRespuesta:
    """Vista privada del cliente: estado, condiciones de la garantía y pases QR."""
    reserva = _reserva_por_token(db, reserva_id, payload.token_cancelacion)
    evento = db.get(EventoModel, reserva.evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento de la reserva no encontrado.")
    pases = reserva_service.pases_de(db, reserva.id) if reserva.estado == "confirmada" else []
    _, usados = reserva_service.conteo_pases(db, reserva.id)
    return ReservaClienteRespuesta(
        id=reserva.id,
        estado=reserva.estado,
        tipo=reserva.tipo,
        asistentes=reserva.asistentes,
        nombre_cliente=reserva.nombre_cliente,
        evento_nombre=evento.nombre,
        evento_fecha=evento.fecha,
        evento_tematica=evento.tematica,
        flyer_url=evento.flyer_url,
        garantizada=bool(reserva.codigo_garantia) and reserva.estado == "confirmada",
        codigo_garantia=reserva.codigo_garantia,
        hora_limite=reserva.hora_limite,
        ubicacion_asignada=reserva.ubicacion_asignada,
        consumo_minimo=reserva.consumo_minimo,
        pases=[
            PaseReservaRespuesta(id=p.id, nombre=p.nombre, qr_code=p.qr_code, estado=p.estado)
            for p in pases
        ],
        puede_cancelar=reserva.estado != "cancelada" and usados == 0,
    )


@router.post("/{reserva_id}/cancelar", response_model=ReservaRespuesta)
def cancelar_solicitud_cliente(
    reserva_id: int,
    payload: ReservaCancelar,
    db: Session = Depends(get_db),
) -> ReservaRespuesta:
    """Permite cancelar una solicitud usando el secreto entregado al crearla."""
    reserva = _reserva_por_token(db, reserva_id, payload.token_cancelacion)
    evento = db.get(EventoModel, reserva.evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento de la reserva no encontrado.")
    reserva_service.cancelar(db, reserva, origen="solicitado por el cliente")
    return _respuesta(reserva, evento.nombre)


@router.get(
    "",
    response_model=list[ReservaRespuesta],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def listar_solicitudes(db: Session = Depends(get_db)) -> list[ReservaRespuesta]:
    stmt = (
        select(ReservaModel, EventoModel.nombre, UsuarioModel.nombre)
        .join(EventoModel, ReservaModel.evento_id == EventoModel.id)
        .outerjoin(UsuarioModel, ReservaModel.promotor_id == UsuarioModel.id)
        .order_by(ReservaModel.fecha_solicitud.desc(), ReservaModel.id.desc())
        .limit(200)
    )
    return _respuestas(db, db.execute(stmt).all())


@router.get(
    "/{reserva_id}/pases",
    response_model=list[PaseReservaRespuesta],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def listar_pases_de_reserva(reserva_id: int, db: Session = Depends(get_db)) -> list[PaseReservaRespuesta]:
    if db.get(ReservaModel, reserva_id) is None:
        raise HTTPException(status_code=404, detail="Solicitud de reserva no encontrada.")
    return [
        PaseReservaRespuesta(id=p.id, nombre=p.nombre, qr_code=p.qr_code, estado=p.estado)
        for p in reserva_service.pases_de(db, reserva_id)
    ]


@router.patch(
    "/{reserva_id}/estado",
    response_model=ReservaRespuesta,
)
def actualizar_estado_reserva(
    reserva_id: int,
    payload: ReservaEstadoActualizar,
    admin: Usuario = Depends(require_roles(RolUsuario.ADMINISTRADOR)),
    db: Session = Depends(get_db),
) -> ReservaRespuesta:
    reserva = db.get(ReservaModel, reserva_id)
    if reserva is None:
        raise HTTPException(status_code=404, detail="Solicitud de reserva no encontrada.")
    evento = db.get(EventoModel, reserva.evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento de la reserva no encontrado.")

    if payload.estado == EstadoReserva.CONFIRMADA:
        era_garantizada = bool(reserva.codigo_garantia) and reserva.estado == "confirmada"
        reserva_service.garantizar(
            db,
            reserva,
            admin_id=admin.id,
            ubicacion_asignada=payload.ubicacion_asignada,
            hora_limite=payload.hora_limite,
            consumo_minimo=payload.consumo_minimo,
            forzar_cupo=payload.forzar_cupo,
        )
        db.refresh(reserva)
        if not era_garantizada:
            _enviar_confirmacion(db, reserva, evento)
    elif payload.estado == EstadoReserva.CANCELADA:
        if reserva.estado != "cancelada":
            reserva_service.cancelar(db, reserva, origen="cancelada por el equipo")
    else:
        if reserva.estado == "confirmada" and reserva.codigo_garantia:
            raise HTTPException(
                status_code=409,
                detail="Una reserva garantizada no vuelve a pendiente; cancélala si ya no aplica.",
            )
        reserva.estado = payload.estado.value
        db.commit()
        db.refresh(reserva)
    return _respuesta(reserva, evento.nombre, conteo=reserva_service.conteo_pases(db, reserva.id))


@router.post(
    "/{reserva_id}/reenviar-confirmacion",
    response_model=ReservaRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def reenviar_confirmacion_reserva(reserva_id: int, db: Session = Depends(get_db)) -> ReservaRespuesta:
    reserva = db.get(ReservaModel, reserva_id)
    if reserva is None:
        raise HTTPException(status_code=404, detail="Solicitud de reserva no encontrada.")
    if reserva.estado != EstadoReserva.CONFIRMADA.value:
        raise HTTPException(status_code=409, detail="Confirma la reserva antes de enviar el aviso al cliente.")
    evento = db.get(EventoModel, reserva.evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento de la reserva no encontrado.")
    _enviar_confirmacion(db, reserva, evento)
    return _respuesta(reserva, evento.nombre, conteo=reserva_service.conteo_pases(db, reserva.id))


@router.delete(
    "/{reserva_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def eliminar_reserva_cancelada(reserva_id: int, db: Session = Depends(get_db)) -> None:
    reserva = db.get(ReservaModel, reserva_id)
    if reserva is None:
        raise HTTPException(status_code=404, detail="Solicitud de reserva no encontrada.")
    if reserva.estado != EstadoReserva.CANCELADA.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden eliminar solicitudes canceladas.",
        )
    db.delete(reserva)
    db.commit()
