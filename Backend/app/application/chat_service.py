"""Persistencia de las conversaciones del asistente.

Privacidad: en la web se guarda el texto (para que el equipo pueda atender escalamientos);
en WhatsApp solo se guarda *metadata* de sentimiento y el teléfono como hash, igual que el
resto del módulo de WhatsApp.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.application.chatbot import ResultadoTurno, estado_inicial
from app.infrastructure.models.chat_model import ChatMensajeModel, ChatSesionModel

VENTANA_WHATSAPP = timedelta(hours=6)
RETENCION_DIAS = 60


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def hash_contacto(valor: str) -> str:
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


def purgar_antiguas(db: Session, dias: int = RETENCION_DIAS, limite: int = 200) -> int:
    limite_fecha = _ahora() - timedelta(days=dias)
    ids = [
        fila[0]
        for fila in db.execute(
            select(ChatSesionModel.id).where(ChatSesionModel.actualizada_en < limite_fecha).limit(limite)
        )
    ]
    if not ids:
        return 0
    db.execute(delete(ChatMensajeModel).where(ChatMensajeModel.sesion_id.in_(ids)))
    db.execute(delete(ChatSesionModel).where(ChatSesionModel.id.in_(ids)))
    db.commit()
    return len(ids)


def _nueva_sesion(db: Session, canal: str, contacto_hash: str | None, estado: dict) -> ChatSesionModel:
    sesion = ChatSesionModel(
        id=str(uuid.uuid4()),
        canal=canal,
        contacto_hash=contacto_hash,
        estado_dialogo=json.dumps(estado, ensure_ascii=False),
        creada_en=_ahora(),
        actualizada_en=_ahora(),
    )
    db.add(sesion)
    db.commit()
    db.refresh(sesion)
    return sesion


def obtener_sesion_web(
    db: Session, sesion_id: str | None, *, promotor_id: int | None = None
) -> ChatSesionModel:
    """Recupera la sesión web; si no existe (o no se envió) crea una nueva con id del servidor."""
    if sesion_id:
        sesion = db.get(ChatSesionModel, sesion_id)
        if sesion is not None and sesion.canal == "web":
            return sesion
    purgar_antiguas(db, limite=25)
    estado = estado_inicial()
    estado["promotor_id"] = promotor_id
    return _nueva_sesion(db, "web", None, estado)


def obtener_sesion_whatsapp(db: Session, remitente: str) -> ChatSesionModel:
    contacto = hash_contacto(remitente)
    sesion = db.execute(
        select(ChatSesionModel)
        .where(ChatSesionModel.contacto_hash == contacto, ChatSesionModel.canal == "whatsapp")
        .order_by(ChatSesionModel.actualizada_en.desc())
        .limit(1)
    ).scalar_one_or_none()
    if sesion is not None:
        actualizada = sesion.actualizada_en
        if actualizada.tzinfo is None:
            actualizada = actualizada.replace(tzinfo=timezone.utc)
        if _ahora() - actualizada <= VENTANA_WHATSAPP:
            return sesion
    return _nueva_sesion(db, "whatsapp", contacto, estado_inicial())


def estado_de(sesion: ChatSesionModel) -> dict:
    try:
        datos = json.loads(sesion.estado_dialogo or "{}")
    except json.JSONDecodeError:
        datos = {}
    return datos if isinstance(datos, dict) else {}


def historial(db: Session, sesion_id: str, limite: int = 10) -> list[tuple[str, str]]:
    filas = db.execute(
        select(ChatMensajeModel.autor, ChatMensajeModel.texto)
        .where(ChatMensajeModel.sesion_id == sesion_id, ChatMensajeModel.texto.is_not(None))
        .order_by(ChatMensajeModel.id.desc())
        .limit(limite)
    ).all()
    return [(autor, texto) for autor, texto in reversed(filas)]


def guardar_turno(
    db: Session,
    sesion: ChatSesionModel,
    *,
    texto_usuario: str,
    resultado: ResultadoTurno,
) -> None:
    guarda_texto = sesion.canal == "web"
    a = resultado.analisis
    aspectos = ",".join(f"{x['aspecto']}:{x['sentimiento']}" for x in a.get("aspectos", []))[:200]
    puntaje = Decimal(str(round(float(a.get("puntaje", 0)), 2)))
    db.add(
        ChatMensajeModel(
            sesion_id=sesion.id,
            autor="usuario",
            texto=texto_usuario if guarda_texto else None,
            sentimiento=a.get("etiqueta"),
            puntaje=puntaje,
            emocion=a.get("emocion"),
            aspectos=aspectos or None,
            intencion=resultado.intencion,
        )
    )
    for mensaje in resultado.mensajes:
        db.add(ChatMensajeModel(sesion_id=sesion.id, autor="bot", texto=mensaje.texto if guarda_texto else None))

    anteriores = sesion.mensajes_total or 0
    promedio = Decimal(sesion.sentimiento_promedio or 0)
    sesion.sentimiento_promedio = (((promedio * anteriores) + puntaje) / (anteriores + 1)).quantize(Decimal("0.01"))
    sesion.mensajes_total = anteriores + 1
    if a.get("etiqueta") == "negativo":
        sesion.negativos = (sesion.negativos or 0) + 1
    if resultado.escalada and not sesion.escalada:
        sesion.escalada = True
    if resultado.reserva and not resultado.reserva.simulada:
        sesion.reserva_id = resultado.reserva.id
    sesion.estado_dialogo = json.dumps(resultado.estado, ensure_ascii=False)
    sesion.actualizada_en = _ahora()
    db.commit()
