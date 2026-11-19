from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _endpoint() -> str:
    settings = get_settings()
    return (
        f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().whatsapp_access_token}"}


def _telefono_internacional(valor: object) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def destinatarios(valor: object) -> list[str]:
    """Lista de teléfonos desde ``"573001112233, 573204445566"`` (coma, punto y coma o salto de línea), sin repetir."""
    vistos: dict[str, None] = {}
    for trozo in re.split(r"[,;\n]+", str(valor or "")):
        numero = _telefono_internacional(trozo)
        if len(numero) >= 10:
            vistos[numero] = None
    return list(vistos)


def _enviar_plantilla(
    nombre: str,
    idioma: str,
    destinatario: str,
    parametros: list[str],
    *,
    componentes_extra: list[dict[str, Any]] | None = None,
) -> tuple[str, str | None, str | None]:
    settings = get_settings()
    if not all((settings.whatsapp_phone_number_id, settings.whatsapp_access_token, nombre)):
        return ("sin_configurar", "Faltan credenciales o el nombre de la plantilla aprobada.", None)

    numero = _telefono_internacional(destinatario)
    if len(numero) < 10:
        return ("fallida", "El teléfono no tiene formato internacional válido.", None)

    componentes: list[dict[str, Any]] = [
        {
            "type": "body",
            "parameters": [{"type": "text", "text": value} for value in parametros],
        }
    ]
    componentes.extend(componentes_extra or [])
    body = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": nombre,
            "language": {"code": idioma},
            "components": componentes,
        },
    }

    try:
        response = httpx.post(_endpoint(), headers=_headers(), json=body, timeout=10.0)
        response.raise_for_status()
        message = (response.json().get("messages") or [{}])[0]
        message_id = message.get("id")
        if not message_id:
            return ("fallida", "Meta no devolvió un identificador de mensaje.", None)
        return ("enviada", None, str(message_id))
    except httpx.HTTPStatusError as exc:
        codigo, mensaje = _error_de_meta(exc.response)
        detalle = f"Meta rechazó el mensaje (HTTP {exc.response.status_code}, código {codigo}): {mensaje}"
        logger.error("Plantilla de WhatsApp «%s» (%s): %s", nombre, idioma, detalle)
        return ("fallida", detalle, None)
    except (httpx.HTTPError, ValueError):
        logger.exception("Falló el envío de una plantilla de WhatsApp.")
        return ("fallida", "No se pudo conectar con WhatsApp. Puedes reintentar.", None)


def _error_de_meta(response: httpx.Response) -> tuple[str, str]:
    """Extrae el código y el mensaje del error de la Graph API (nunca incluye el token)."""
    try:
        error = response.json().get("error") or {}
    except ValueError:
        return ("?", (response.text or "sin detalle")[:200])
    detalle = (error.get("error_data") or {}).get("details")
    mensaje = str(error.get("message") or "sin detalle")
    if detalle:
        mensaje = f"{mensaje} — {detalle}"
    return (str(error.get("code", "?")), mensaje[:300])


def _faltantes_aviso() -> list[str]:
    s = get_settings()
    requeridos = {
        "WHATSAPP_PHONE_NUMBER_ID": s.whatsapp_phone_number_id,
        "WHATSAPP_ACCESS_TOKEN": s.whatsapp_access_token,
        "WHATSAPP_TEMPLATE_NAME": s.whatsapp_template_name,
        "WHATSAPP_NOTIFY_TO": s.whatsapp_notify_to,
    }
    return [nombre for nombre, valor in requeridos.items() if not valor]


def diagnosticar_aviso_reserva() -> dict[str, Any]:
    """Revisa de punta a punta el aviso de nueva reserva y envía la plantilla real con datos de prueba.

    Pensado para el panel del administrador: explica EN QUÉ paso falla (configuración, token, número o
    plantilla/destinatario) sin necesidad de revisar logs. Nunca devuelve el token.
    """
    from app.core.tareas import es_serverless

    s = get_settings()
    pasos: list[dict[str, Any]] = []

    def paso(clave: str, titulo: str, ok: bool, detalle: str) -> bool:
        pasos.append({"clave": clave, "titulo": titulo, "ok": ok, "detalle": detalle})
        return ok

    faltan = _faltantes_aviso()
    if not paso(
        "configuracion", "Variables de entorno", not faltan,
        "Completas." if not faltan else f"Faltan: {', '.join(faltan)}. En Vercel: Settings → Environment Variables, y vuelve a desplegar.",
    ):
        return {"ok": False, "pasos": pasos}

    paso("entorno", "Entorno de ejecución", True,
         "Serverless: los avisos se envían antes de responder." if es_serverless() else "Servidor tradicional: los avisos salen en segundo plano.")

    base = f"https://graph.facebook.com/{s.whatsapp_graph_api_version}"
    try:
        r = httpx.get(f"{base}/debug_token", params={"input_token": s.whatsapp_access_token}, headers=_headers(), timeout=10.0)
        if r.status_code != 200:
            codigo, mensaje = _error_de_meta(r)
            paso("token", "Token de acceso", False, f"Meta lo rechazó (código {codigo}): {mensaje}. Genera un token permanente de usuario del sistema.")
            return {"ok": False, "pasos": pasos}
        datos = r.json().get("data") or {}
        if not datos.get("is_valid"):
            paso("token", "Token de acceso", False, "El token no es válido o venció. Genera uno nuevo (usuario del sistema, caducidad «Nunca»).")
            return {"ok": False, "pasos": pasos}
        permisos = set(datos.get("scopes") or [])
        faltan_permisos = {"whatsapp_business_messaging"} - permisos
        paso("token", "Token de acceso", not faltan_permisos,
             ("Válido" + (", sin vencimiento." if not datos.get("expires_at") else ".")) if not faltan_permisos
             else f"Válido pero sin el permiso: {', '.join(sorted(faltan_permisos))}.")

        r = httpx.get(f"{base}/{s.whatsapp_phone_number_id}", params={"fields": "display_phone_number,verified_name,quality_rating"},
                      headers=_headers(), timeout=10.0)
        if r.status_code != 200:
            codigo, mensaje = _error_de_meta(r)
            paso("numero", "Número de WhatsApp (Phone Number ID)", False, f"No se pudo leer (código {codigo}): {mensaje}")
            return {"ok": False, "pasos": pasos}
        n = r.json()
        paso("numero", "Número de WhatsApp (Phone Number ID)", True,
             f"{n.get('display_phone_number')} · {n.get('verified_name')} · calidad {n.get('quality_rating')}")
    except httpx.HTTPError as exc:
        paso("red", "Conexión con Meta", False, f"No se pudo conectar con graph.facebook.com ({type(exc).__name__}).")
        return {"ok": False, "pasos": pasos}

    ultimo_evento = _ultimo_evento_meta()
    paso("webhook", "Webhook de Meta (reporta si el mensaje se entrega)", ultimo_evento is not None,
         f"Meta reportó su último evento el {ultimo_evento:%d/%m/%Y %H:%M} UTC." if ultimo_evento else
         "Meta nunca ha enviado un evento a este sistema. En Meta → WhatsApp → Configuración → Webhook: URL "
         "«/webhooks/whatsapp» de este sitio, el mismo token de verificación, y suscribe el campo «messages». "
         "Sin esto no se puede saber si los mensajes se entregan.")

    lista = destinatarios(s.whatsapp_notify_to)
    paso("destinos", "Destinatarios de los avisos", bool(lista),
         f"{len(lista)} teléfono(s): " + ", ".join("…" + n[-4:] for n in lista) if lista else
         "WHATSAPP_NOTIFY_TO no tiene ningún teléfono válido (con indicativo, p. ej. 573001112233; varios separados por coma).")
    enviados: list[tuple[str, str]] = []
    for destino in lista:
        etiqueta = "…" + destino[-4:]
        estado, error, message_id = _enviar_plantilla(
            s.whatsapp_template_name, s.whatsapp_template_language, destino,
            ["0", "PRUEBA de diagnóstico", destino, "Prueba del panel", "Mesa", "2", "Panel del administrador", "Mensaje de prueba, ignorar"],
        )
        aceptado = estado == "enviada"
        paso(f"envio_{destino[-4:]}", f"Envío a {etiqueta} · plantilla «{s.whatsapp_template_name}» ({s.whatsapp_template_language})", aceptado,
             f"Meta aceptó el mensaje ({message_id})." if aceptado else (error or "No se pudo enviar."))
        if aceptado:
            enviados.append((destino, str(message_id)))

    espera = 10.0 if ultimo_evento else 3.0
    for destino, message_id in enviados:
        eventos = _esperar_estados(message_id, segundos=espera)
        espera = 1.0  # los siguientes ya tuvieron tiempo mientras se esperaba al primero
        etiqueta = "…" + destino[-4:]
        if any(e.estado == "failed" for e in eventos):
            e = next(e for e in eventos if e.estado == "failed")
            paso(f"entrega_{destino[-4:]}", f"Entrega a {etiqueta}", False,
                 f"FALLÓ (código {e.codigo_error or '?'}): {_causa_error_entrega(e.codigo_error, e.titulo_error)}")
        elif any(e.estado in {"delivered", "read"} for e in eventos):
            paso(f"entrega_{destino[-4:]}", f"Entrega a {etiqueta}", True, "Meta confirmó la entrega: el mensaje llegó al teléfono.")
        elif eventos:
            paso(f"entrega_{destino[-4:]}", f"Entrega a {etiqueta}", False,
                 "Meta lo envió a WhatsApp («sent») pero aún no confirma la entrega. Revisa el teléfono; si no llega, "
                 "vuelve a diagnosticar para ver el motivo que reporte Meta.")
        else:
            paso(f"entrega_{destino[-4:]}", f"Entrega a {etiqueta}", False,
                 "Meta aún no reportó el estado de este mensaje. " + (
                     "Puede tardar unos segundos: vuelve a pulsar el diagnóstico." if ultimo_evento else
                     "Conecta el webhook (paso anterior) para ver aquí si se entregó o por qué falló."))
    return {"ok": all(p["ok"] for p in pasos), "pasos": pasos}


# Causas y soluciones de los códigos de error más comunes de la API de WhatsApp Cloud.
_CAUSAS_META = {
    "131030": "El número de destino no está en la lista de destinatarios permitidos del número de PRUEBA de Meta. "
              "Solución: Meta → WhatsApp → Configuración de la API → campo «Para» → «Administrar lista de números», "
              "agrega el número y confirma el código que llega por WhatsApp.",
    "131026": "Meta no pudo entregar el mensaje: ese número no tiene WhatsApp activo o no puede recibir mensajes de empresas. "
              "Solución: confirma que el número es el de WhatsApp de la persona y que tiene la app actualizada.",
    "131049": "Meta decidió no entregarlo para proteger la calidad de la plataforma (frecuente con números/cuentas nuevas). "
              "Solución: reintenta más tarde, o que el destinatario escriba primero al número de la empresa.",
    "131047": "Pasaron más de 24 h desde el último mensaje del usuario: solo se permiten plantillas aprobadas.",
    "131042": "Problema de facturación en la cuenta de WhatsApp Business. Solución: agrega un método de pago en WhatsApp Manager.",
    "131031": "La cuenta de WhatsApp Business está restringida o bloqueada. Revísala en WhatsApp Manager.",
    "131056": "Se enviaron demasiados mensajes seguidos al mismo número. Espera unos minutos.",
    "130429": "Se superó el límite de mensajes por segundo de la API.",
    "132000": "La cantidad de parámetros enviados no coincide con la plantilla aprobada.",
    "132001": "La plantilla no existe en ese idioma. Solución: usa el mismo idioma con el que Meta la aprobó.",
    "132012": "Algún parámetro de la plantilla tiene un formato inválido.",
    "132015": "La plantilla está pausada por baja calidad. Revísala en WhatsApp Manager.",
    "132016": "La plantilla fue deshabilitada por Meta.",
    "190": "El token de acceso venció o fue revocado. Solución: genera un token permanente de usuario del sistema.",
}


def _causa_error_entrega(codigo: str | None, titulo: str | None) -> str:
    return _CAUSAS_META.get(str(codigo), titulo or "Meta no entregó el mensaje y no informó el motivo.")


def _sesion_bd():
    from app.infrastructure.database.session import SessionLocal

    return SessionLocal()


def _ultimo_evento_meta():
    """Fecha del último estado de entrega recibido de Meta, o None si el webhook nunca ha llegado."""
    from sqlalchemy import func, select

    from app.infrastructure.models.whatsapp_estado_model import WhatsAppEstadoModel

    try:
        with _sesion_bd() as db:
            return db.execute(select(func.max(WhatsAppEstadoModel.creado_en))).scalar()
    except Exception:  # la tabla puede no existir aún (migración pendiente)
        logger.exception("No se pudo consultar los estados de entrega de WhatsApp.")
        return None


def _esperar_estados(message_id: str, segundos: float):
    """Espera hasta ``segundos`` a que Meta reporte (por webhook) el estado final del mensaje."""
    import time

    from sqlalchemy import select

    from app.infrastructure.models.whatsapp_estado_model import WhatsAppEstadoModel

    limite = time.monotonic() + segundos
    eventos: list = []
    while True:
        try:
            with _sesion_bd() as db:
                eventos = list(db.execute(
                    select(WhatsAppEstadoModel).where(WhatsAppEstadoModel.message_id == message_id).order_by(WhatsAppEstadoModel.id)
                ).scalars())
        except Exception:
            logger.exception("No se pudo leer el estado del mensaje %s.", message_id)
            return []
        if any(e.estado in {"delivered", "read", "failed"} for e in eventos) or time.monotonic() >= limite:
            return eventos
        time.sleep(1.0)


def notificar_confirmacion_reserva(
    datos: dict[str, str | int],
) -> tuple[str, str | None, str | None]:
    """Send customer confirmation; delivery is confirmed later by webhook status."""
    settings = get_settings()
    if not settings.whatsapp_confirmation_template_name:
        return ("sin_configurar", "Configura una plantilla aprobada para confirmar al cliente.", None)
    parametros = [
        str(datos["nombre_cliente"]),
        str(datos["evento_nombre"]),
        str(datos["tipo"]),
        str(datos["asistentes"]),
        str(datos["id"]),
    ]
    return _enviar_plantilla(
        settings.whatsapp_confirmation_template_name,
        settings.whatsapp_confirmation_template_language,
        str(datos["telefono"]),
        parametros,
    )


def notificar_stock_bajo(datos: dict[str, str | int | float]) -> None:
    """Notify the configured operator when an item crosses below its minimum."""
    settings = get_settings()
    plantilla = settings.whatsapp_inventory_template_name
    destinatario = settings.whatsapp_inventory_notify_to or settings.whatsapp_notify_to
    if not plantilla or not destinatario:
        logger.info("Aviso de stock bajo omitido: configura destinatario y plantilla de inventario.")
        return
    unidad = str(datos["unidad"])
    parametros = [
        str(datos["nombre"]),
        f'{datos["cantidad"]} {unidad}',
        f'{datos["stock_minimo"]} {unidad}',
        str(datos.get("categoria") or "General"),
    ]
    for destino in destinatarios(destinatario):
        estado, error, _ = _enviar_plantilla(
            plantilla,
            settings.whatsapp_inventory_template_language,
            destino,
            parametros,
        )
        if estado != "enviada":
            logger.warning("No se pudo avisar el stock bajo a ...%s: %s", destino[-4:], error)


def responder_mensaje_bot_whatsapp(destinatario: str, texto: str) -> tuple[str, str | None]:
    settings = get_settings()
    if not all((settings.whatsapp_phone_number_id, settings.whatsapp_access_token)):
        return ("sin_configurar", "Faltan credenciales de WhatsApp Cloud API.")
    numero = _telefono_internacional(destinatario)
    if len(numero) < 10:
        return ("fallida", "El remitente no tiene formato internacional válido.")
    body = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"preview_url": False, "body": texto[:4096]},
    }
    try:
        response = httpx.post(_endpoint(), headers=_headers(), json=body, timeout=10.0)
        response.raise_for_status()
        return ("respondido", None)
    except httpx.HTTPStatusError as exc:
        logger.error("Meta rechazó la respuesta del bot (HTTP %s).", exc.response.status_code)
        return ("fallida", f"Meta rechazó la respuesta (HTTP {exc.response.status_code}).")
    except httpx.HTTPError:
        logger.exception("Falló el envío de respuesta del bot.")
        return ("fallida", "No se pudo conectar con WhatsApp.")


def notificar_nueva_reserva(datos: dict[str, str | int]) -> None:
    """Send the configured internal reservation template."""
    settings = get_settings()
    if not all(
        (
            settings.whatsapp_phone_number_id,
            settings.whatsapp_access_token,
            settings.whatsapp_notify_to,
            settings.whatsapp_template_name,
        )
    ):
        logger.warning("Aviso de nueva reserva omitido: faltan variables de entorno: %s.", ", ".join(_faltantes_aviso()))
        return

    parametros = [
        str(datos["id"]),
        str(datos["nombre_cliente"]),
        str(datos["telefono"]),
        str(datos["evento_nombre"]),
        str(datos["tipo"]),
        str(datos["asistentes"]),
        str(datos["promotor"]),
        str(datos["notas"]),
    ]
    componentes_extra: list[dict[str, Any]] = []
    if settings.whatsapp_reservation_url_prefix:
        componentes_extra.append(
            {
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [{"type": "text", "text": str(datos["id"])}],
            }
        )
    for destino in destinatarios(settings.whatsapp_notify_to):
        estado, error, _ = _enviar_plantilla(
            settings.whatsapp_template_name,
            settings.whatsapp_template_language,
            destino,
            parametros,
            componentes_extra=componentes_extra,
        )
        if estado != "enviada":  # un destinatario con problemas no impide avisar a los demás
            logger.warning("No se pudo enviar el aviso de nueva reserva a ...%s: %s", destino[-4:], error)


def enviar_aviso_prueba(telefono: str) -> tuple[str, str | None]:
    """Envía la plantilla aprobada con datos de prueba a un teléfono (no depende de la ventana de 24 h)."""
    s = get_settings()
    numero = _telefono_internacional(telefono)
    estado, error, _ = _enviar_plantilla(
        s.whatsapp_template_name, s.whatsapp_template_language, numero,
        ["0", "PRUEBA del panel", numero, "Prueba de conexión", "Mesa", "2", "Panel del administrador", "Mensaje de prueba, ignorar"],
    )
    return estado, error
