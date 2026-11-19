from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application import chat_service
from app.application.chatbot import Asistente, a_texto_whatsapp
from app.application.sentiment_service import analizar_sentimiento
from app.application.whatsapp_notification_service import (
    notificar_nueva_reserva,
    responder_mensaje_bot_whatsapp,
)
from app.core.config import get_settings
from app.infrastructure.database.session import get_db
from app.infrastructure.models.reserva_model import ReservaModel
from app.infrastructure.models.whatsapp_estado_model import WhatsAppEstadoModel
from app.infrastructure.models.whatsapp_inbound_message_model import WhatsAppInboundMessageModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["WhatsApp Cloud API"])


@router.get("/whatsapp", response_class=PlainTextResponse)
def verificar_webhook_whatsapp(
    modo: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    settings = get_settings()
    if not settings.whatsapp_webhook_verify_token:
        raise HTTPException(status_code=503, detail="Configura WHATSAPP_WEBHOOK_VERIFY_TOKEN.")
    if (
        modo == "subscribe"
        and token
        and hmac.compare_digest(token, settings.whatsapp_webhook_verify_token)
        and challenge is not None
    ):
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verificación de webhook inválida.")


def _validar_firma(body: bytes, firma: str | None, app_secret: str) -> bool:
    if not firma or not app_secret or not firma.startswith("sha256="):
        return False
    esperado = "sha256=" + hmac.new(
        app_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(firma, esperado)


def _texto_entrante(mensaje: dict[str, Any]) -> str:
    tipo = mensaje.get("type")
    if tipo == "text":
        return str((mensaje.get("text") or {}).get("body") or "").strip()
    if tipo == "button":
        return str((mensaje.get("button") or {}).get("text") or "").strip()
    if tipo == "interactive":
        interactive = mensaje.get("interactive") or {}
        button = interactive.get("button_reply") or {}
        item = interactive.get("list_reply") or {}
        return str(button.get("title") or item.get("title") or "").strip()
    return ""


def _guardar_estado(db: Session, estado_webhook: dict[str, Any]) -> None:
    """Conserva el estado de entrega (con el código de error de Meta) para poder diagnosticar los avisos."""
    errores = estado_webhook.get("errors") or []
    error = errores[0] if errores and isinstance(errores[0], dict) else {}
    destino = re.sub(r"\D", "", str(estado_webhook.get("recipient_id") or ""))
    db.add(
        WhatsAppEstadoModel(
            message_id=str(estado_webhook["id"])[:255],
            estado=str(estado_webhook["status"])[:20],
            destinatario_fin=destino[-4:] or None,
            codigo_error=str(error.get("code"))[:20] if error.get("code") is not None else None,
            titulo_error=str(error.get("title") or error.get("message") or "")[:300] or None,
            detalle_error=str((error.get("error_data") or {}).get("details") or "")[:1000] or None,
        )
    )
    db.commit()


def _registrar_estado_entrega(db: Session, estado_webhook: dict[str, Any]) -> None:
    message_id = estado_webhook.get("id")
    status_value = estado_webhook.get("status")
    if not message_id or status_value not in {"sent", "delivered", "read", "failed"}:
        return
    _guardar_estado(db, estado_webhook)

    reserva = db.execute(
        select(ReservaModel).where(
            ReservaModel.whatsapp_confirmacion_message_id == str(message_id)
        )
    ).scalar_one_or_none()
    if reserva is None:
        return

    estados = {
        "sent": "enviada",
        "delivered": "entregada",
        "read": "leida",
        "failed": "fallida",
    }
    nuevo = estados[status_value]
    prioridad = {"sin_configurar": 0, "fallida": 0, "enviada": 1, "entregada": 2, "leida": 3}
    actual = reserva.whatsapp_confirmacion_estado
    if nuevo == "fallida" or prioridad.get(nuevo, 0) > prioridad.get(actual, 0):
        reserva.whatsapp_confirmacion_estado = nuevo
        errores = estado_webhook.get("errors") or []
        detalle = (errores[0] or {}).get("title") if errores else None
        reserva.whatsapp_confirmacion_error = (
            str(detalle or "Meta no pudo entregar la confirmación.")
            if nuevo == "fallida"
            else None
        )
        db.commit()


def _procesar_mensaje(db: Session, mensaje: dict[str, Any], reserva_url: str = "") -> None:
    message_id = str(mensaje.get("id") or "").strip()
    remitente = str(mensaje.get("from") or "").strip()
    texto = _texto_entrante(mensaje)
    if not message_id or not remitente:
        return

    existente = db.get(WhatsAppInboundMessageModel, message_id)
    if existente and existente.response_status not in {"fallida", "sin_configurar"}:
        return

    if existente is not None:
        # Reintento de una entrega cuya respuesta falló: NO se vuelve a ejecutar el asistente
        # (evita duplicar reservas o avisos); solo se reenvía una respuesta segura.
        estado, error = responder_mensaje_bot_whatsapp(
            remitente, "Recibimos tu mensaje. Escribe MENÚ para ver las opciones disponibles."
        )
        existente.response_status = estado
        db.commit()
        if estado != "respondido":
            logger.warning("El bot no pudo responder al mensaje %s: %s", message_id, error)
        return

    sesion = chat_service.obtener_sesion_whatsapp(db, remitente)
    asistente = Asistente(
        db, canal="whatsapp", contacto_tel=remitente, url_reservas=reserva_url, sesion_id=sesion.id
    )
    if texto:
        resultado = asistente.turno(chat_service.estado_de(sesion), texto, None)
        respuesta = a_texto_whatsapp(resultado.mensajes)
    else:
        resultado = asistente.turno(chat_service.estado_de(sesion), None, "inicio")
        resultado.analisis = {**analizar_sentimiento("mensaje sin texto")}
        respuesta = "Por ahora puedo responder mensajes de texto.\n\n" + a_texto_whatsapp(resultado.mensajes)
    analisis = resultado.analisis

    entrada = WhatsAppInboundMessageModel(
        message_id=message_id,
        sender_hash=hashlib.sha256(remitente.encode("utf-8")).hexdigest(),
        sentiment=analisis["etiqueta"],
        score=analisis["puntaje"],
        response_status="procesando",
    )
    db.add(entrada)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return

    chat_service.guardar_turno(db, sesion, texto_usuario=texto, resultado=resultado)
    if resultado.reserva and resultado.reserva.datos_notificacion:
        notificar_nueva_reserva(resultado.reserva.datos_notificacion)

    estado, error = responder_mensaje_bot_whatsapp(remitente, respuesta)
    entrada = db.get(WhatsAppInboundMessageModel, message_id)
    if entrada:
        entrada.response_status = estado
        db.commit()
    if estado != "respondido":
        logger.warning("El bot no pudo responder al mensaje %s: %s", message_id, error)


def _procesar_payload(db: Session, payload: dict[str, Any], reserva_url: str = "") -> None:
    if payload.get("object") != "whatsapp_business_account":
        return
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for estado in value.get("statuses") or []:
                _registrar_estado_entrega(db, estado)
            for mensaje in value.get("messages") or []:
                _procesar_mensaje(db, mensaje, reserva_url)


@router.post("/whatsapp")
async def recibir_webhook_whatsapp(
    request: Request,
    firma: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    settings = get_settings()
    if not settings.whatsapp_app_secret:
        raise HTTPException(status_code=503, detail="Configura WHATSAPP_APP_SECRET.")
    body = await request.body()
    if not _validar_firma(body, firma, settings.whatsapp_app_secret):
        raise HTTPException(status_code=401, detail="Firma de webhook inválida.")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="El webhook no contiene JSON válido.") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Formato de webhook no válido.")
    reserva_url = (getattr(settings, "whatsapp_reservation_page_url", "") or "").strip()
    _procesar_payload(db, payload, reserva_url)
    return {"status": "ok"}


@router.get("/whatsapp/health")
def estado_webhook_whatsapp() -> dict[str, str]:
    settings = get_settings()
    return {
        "verify_token": "configurado" if settings.whatsapp_webhook_verify_token else "pendiente",
        "app_secret": "configurado" if settings.whatsapp_app_secret else "pendiente",
    }
