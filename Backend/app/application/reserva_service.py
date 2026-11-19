"""Reglas de negocio de las reservas de mesas y palcos, incluida la reserva garantizada.

Una reserva *garantizada* es una solicitud que el club confirmó y a la cual le asegura:
cupo dentro del aforo del evento, un código de garantía, condiciones claras (ubicación,
hora límite de llegada, consumo mínimo) y un pase QR por cada asistente.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application import notificacion_service
from app.application.invitado_service import generar_qr_code
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.enums import RolUsuario
from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.invitado_model import InvitadoModel
from app.infrastructure.models.reserva_model import ReservaModel
from app.infrastructure.models.usuario_model import UsuarioModel


@dataclass
class SolicitudCreada:
    reserva: ReservaModel
    evento: EventoModel
    promotor: UsuarioModel | None
    token_cancelacion: str


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_valido(reserva: ReservaModel, token: str) -> bool:
    if not reserva.token_cancelacion_hash or not token:
        return False
    return hmac.compare_digest(reserva.token_cancelacion_hash, hash_token(token))


def crear_solicitud(
    db: Session,
    *,
    evento_id: int,
    nombre_cliente: str,
    telefono: str,
    tipo: str,
    asistentes: int,
    notas: str | None = None,
    promotor_id: int | None = None,
) -> SolicitudCreada:
    evento = db.get(EventoModel, evento_id)
    if evento is None or evento.estado != "planeado" or evento.fecha < date.today():
        raise NotFoundError("El evento ya no está disponible para solicitudes de reserva.")

    promotor = None
    if promotor_id is not None:
        promotor = db.get(UsuarioModel, promotor_id)
        if promotor is None or promotor.rol != RolUsuario.PROMOTOR.value or not promotor.estado:
            raise ValidationError("El enlace de promotor no es válido.")

    token = secrets.token_urlsafe(32)
    reserva = ReservaModel(
        evento_id=evento.id,
        promotor_id=promotor.id if promotor else None,
        nombre_cliente=nombre_cliente.strip(),
        telefono=telefono.strip(),
        tipo=tipo,
        asistentes=asistentes,
        notas=notas.strip() if notas else None,
        estado="pendiente",
        token_cancelacion_hash=hash_token(token),
    )
    db.add(reserva)
    db.commit()
    db.refresh(reserva)
    notificacion_service.notificar(
        db,
        tipo="reserva_nueva",
        titulo=f"Nueva solicitud de reserva #{reserva.id}",
        mensaje=(
            f"{reserva.nombre_cliente} pide {'una mesa' if tipo == 'mesa' else 'un palco'} "
            f"para {asistentes} en {evento.nombre}."
        ),
        nivel="info",
        enlace=f"/reservas-admin?reserva={reserva.id}",
        referencia=f"reserva:{reserva.id}",
    )
    return SolicitudCreada(reserva=reserva, evento=evento, promotor=promotor, token_cancelacion=token)


def rotar_token(db: Session, reserva: ReservaModel) -> str:
    """Emite un nuevo enlace privado de gestión (el anterior deja de servir)."""
    token = secrets.token_urlsafe(32)
    reserva.token_cancelacion_hash = hash_token(token)
    db.commit()
    return token


def pases_de(db: Session, reserva_id: int) -> list[InvitadoModel]:
    return list(
        db.execute(
            select(InvitadoModel).where(InvitadoModel.reserva_id == reserva_id).order_by(InvitadoModel.id)
        ).scalars()
    )


def conteo_pases(db: Session, reserva_id: int) -> tuple[int, int]:
    total = db.execute(
        select(func.count()).select_from(InvitadoModel).where(InvitadoModel.reserva_id == reserva_id)
    ).scalar_one()
    usados = db.execute(
        select(func.count())
        .select_from(InvitadoModel)
        .where(InvitadoModel.reserva_id == reserva_id, InvitadoModel.estado == "usado")
    ).scalar_one()
    return int(total), int(usados)


def _codigo_garantia_unico(db: Session, reserva_id: int) -> str:
    for _ in range(10):
        codigo = f"MC-{reserva_id:05d}-{secrets.token_hex(2).upper()}"
        existe = db.execute(
            select(ReservaModel.id).where(ReservaModel.codigo_garantia == codigo)
        ).first()
        if not existe:
            return codigo
    raise ConflictError("No se pudo generar un código de garantía único. Intenta de nuevo.")


def cupo_comprometido(db: Session, evento_id: int) -> int:
    """Pases ya emitidos para el evento (listas de promotores y reservas garantizadas)."""
    return int(
        db.execute(
            select(func.count()).select_from(InvitadoModel).where(InvitadoModel.evento_id == evento_id)
        ).scalar_one()
    )


def garantizar(
    db: Session,
    reserva: ReservaModel,
    *,
    admin_id: int,
    ubicacion_asignada: str | None = None,
    hora_limite: str | None = None,
    consumo_minimo: Decimal | None = None,
    forzar_cupo: bool = False,
) -> list[InvitadoModel]:
    """Confirma la reserva y la convierte en garantizada, emitiendo un pase por asistente."""
    if reserva.estado == "cancelada":
        raise ConflictError("No se puede garantizar una reserva cancelada.")
    existentes = pases_de(db, reserva.id)
    if reserva.codigo_garantia and existentes:
        return existentes  # idempotente: ya estaba garantizada

    evento = db.get(EventoModel, reserva.evento_id)
    if evento is None:
        raise NotFoundError("Evento de la reserva no encontrado.")
    disponible = evento.aforo_maximo - cupo_comprometido(db, evento.id)
    if reserva.asistentes > disponible and not forzar_cupo:
        raise ConflictError(
            f"No hay cupo suficiente para garantizar esta reserva: pide {reserva.asistentes} "
            f"lugares y quedan {max(disponible, 0)} de {evento.aforo_maximo}. "
            "Puedes forzar la confirmación si autorizas exceder el cupo."
        )

    titular = reserva.nombre_cliente
    pases: list[InvitadoModel] = []
    for numero in range(1, reserva.asistentes + 1):
        nombre = titular if numero == 1 else f"Invitado {numero} de {titular}"
        pase = InvitadoModel(
            evento_id=evento.id,
            promotor_id=reserva.promotor_id or admin_id,
            reserva_id=reserva.id,
            nombre=nombre[:100],
            qr_code=generar_qr_code(evento.id),
            estado="pendiente",
        )
        db.add(pase)
        pases.append(pase)

    reserva.estado = "confirmada"
    reserva.codigo_garantia = _codigo_garantia_unico(db, reserva.id)
    reserva.garantizada_en = datetime.now(timezone.utc)
    reserva.ubicacion_asignada = ubicacion_asignada
    reserva.hora_limite = hora_limite
    reserva.consumo_minimo = consumo_minimo
    db.commit()
    for pase in pases:
        db.refresh(pase)

    if reserva.promotor_id:
        notificacion_service.notificar(
            db,
            tipo="reserva_garantizada",
            titulo="Reserva de tu referido garantizada",
            mensaje=(
                f"La reserva de {reserva.nombre_cliente} para {evento.nombre} "
                f"quedó garantizada ({reserva.codigo_garantia})."
            ),
            nivel="info",
            enlace="/promotor/reservas",
            referencia=f"reserva:{reserva.id}",
            usuario_id=reserva.promotor_id,
        )
    return pases


def liberar(db: Session, reserva: ReservaModel) -> int:
    """Retira los pases sin usar de una reserva que se cancela. Devuelve cuántos retiró."""
    total, usados = conteo_pases(db, reserva.id)
    if usados:
        raise ConflictError(
            f"No se puede cancelar: {usados} invitado(s) de esta reserva ya ingresaron al evento."
        )
    retirados = 0
    for pase in pases_de(db, reserva.id):
        db.delete(pase)
        retirados += 1
    return retirados


def cancelar(db: Session, reserva: ReservaModel, *, origen: str) -> ReservaModel:
    if reserva.estado == "cancelada":
        raise ConflictError("Esta solicitud ya está cancelada.")
    liberar(db, reserva)
    reserva.estado = "cancelada"
    db.commit()
    db.refresh(reserva)
    evento = db.get(EventoModel, reserva.evento_id)
    notificacion_service.notificar(
        db,
        tipo="reserva_cancelada",
        titulo=f"Reserva #{reserva.id} cancelada",
        mensaje=(
            f"{reserva.nombre_cliente} canceló su reserva en "
            f"{evento.nombre if evento else 'el evento'} ({origen})."
        ),
        nivel="alerta" if reserva.codigo_garantia else "info",
        enlace=f"/reservas-admin?reserva={reserva.id}",
        referencia=f"reserva:{reserva.id}",
    )
    return reserva


def digitos(telefono: str) -> str:
    return re.sub(r"\D", "", telefono or "")


def coincide_telefono(a: str, b: str) -> bool:
    """Compara teléfonos ignorando formato e indicativo de país (usa los últimos 10 dígitos)."""
    da, db_ = digitos(a), digitos(b)
    return len(da) >= 7 and len(db_) >= 7 and da[-10:] == db_[-10:]
