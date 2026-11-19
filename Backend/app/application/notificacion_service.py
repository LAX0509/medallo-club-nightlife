"""Notificaciones internas del panel (campana). Son independientes de WhatsApp: siempre
quedan registradas, aunque Meta no esté configurado, y se muestran en la interfaz."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.domain.entities.usuario import Usuario
from app.domain.enums import RolUsuario
from app.infrastructure.models.notificacion_model import NotificacionModel

NIVELES = ("info", "alerta", "critica")


def notificar(
    db: Session,
    *,
    tipo: str,
    titulo: str,
    mensaje: str,
    nivel: str = "info",
    enlace: str | None = None,
    referencia: str | None = None,
    rol_destino: str | None = RolUsuario.ADMINISTRADOR.value,
    usuario_id: int | None = None,
    deduplicar: bool = False,
) -> NotificacionModel | None:
    """Crea una notificación. Con ``deduplicar`` evita repetir una igual aún no leída."""
    if nivel not in NIVELES:
        nivel = "info"
    if deduplicar and referencia:
        existente = db.execute(
            select(NotificacionModel.id).where(
                NotificacionModel.tipo == tipo,
                NotificacionModel.referencia == referencia,
                NotificacionModel.leida.is_(False),
            )
        ).first()
        if existente:
            return None
    notificacion = NotificacionModel(
        tipo=tipo,
        titulo=titulo[:120],
        mensaje=mensaje[:400],
        nivel=nivel,
        enlace=enlace,
        referencia=referencia,
        destinatario_rol=None if usuario_id else rol_destino,
        destinatario_usuario_id=usuario_id,
    )
    db.add(notificacion)
    db.commit()
    db.refresh(notificacion)
    return notificacion


def _visibles_para(usuario: Usuario):
    return or_(
        NotificacionModel.destinatario_usuario_id == usuario.id,
        (NotificacionModel.destinatario_usuario_id.is_(None))
        & (NotificacionModel.destinatario_rol == usuario.rol.value),
    )


def listar(
    db: Session, usuario: Usuario, *, solo_no_leidas: bool = False, limite: int = 30
) -> list[NotificacionModel]:
    stmt = select(NotificacionModel).where(_visibles_para(usuario))
    if solo_no_leidas:
        stmt = stmt.where(NotificacionModel.leida.is_(False))
    stmt = stmt.order_by(NotificacionModel.creada_en.desc(), NotificacionModel.id.desc()).limit(limite)
    return list(db.execute(stmt).scalars())


def contar_no_leidas(db: Session, usuario: Usuario) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(NotificacionModel)
            .where(_visibles_para(usuario), NotificacionModel.leida.is_(False))
        ).scalar_one()
    )


def marcar_leida(db: Session, usuario: Usuario, notificacion_id: int) -> bool:
    notificacion = db.get(NotificacionModel, notificacion_id)
    if notificacion is None:
        return False
    es_propia = notificacion.destinatario_usuario_id == usuario.id or (
        notificacion.destinatario_usuario_id is None
        and notificacion.destinatario_rol == usuario.rol.value
    )
    if not es_propia:
        return False
    if not notificacion.leida:
        notificacion.leida = True
        notificacion.leida_en = datetime.now(timezone.utc)
        db.commit()
    return True


def marcar_todas_leidas(db: Session, usuario: Usuario) -> int:
    resultado = db.execute(
        update(NotificacionModel)
        .where(_visibles_para(usuario), NotificacionModel.leida.is_(False))
        .values(leida=True, leida_en=datetime.now(timezone.utc))
    )
    db.commit()
    return int(resultado.rowcount or 0)
