"""Administración del asistente: estado de conexiones, configuración y probadores."""

import re
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.chat_router import a_respuesta
from app.api.v1.deps import get_db, require_roles
from app.application import bot_config
from app.application.chatbot import Asistente, _nuevo_estado
from app.application.ia_client import ClienteIA, IANoDisponible, llamadas_ia_hoy
from app.application.whatsapp_notification_service import (
    diagnosticar_aviso_reserva,
    enviar_aviso_prueba,
    responder_mensaje_bot_whatsapp,
)
from app.core.config import get_settings
from app.domain.enums import RolUsuario
from app.schemas.chat_schema import ChatRespuesta

router = APIRouter(
    prefix="/bot",
    tags=["Configuración del asistente"],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)


class PasoConfiguracion(BaseModel):
    clave: str
    titulo: str
    ok: bool
    detalle: str


class EstadoBot(BaseModel):
    ia_proveedor: str
    ia_configurada: bool
    ia_habilitada: bool
    ia_activa: bool
    ia_modelo: str
    ia_llamadas_hoy: int
    ia_limite_diario: int
    whatsapp_credenciales: bool
    whatsapp_webhook: bool
    whatsapp_plantilla_reservas: bool
    whatsapp_plantilla_confirmacion: bool
    whatsapp_plantilla_inventario: bool
    whatsapp_destino_avisos: bool
    webhook_ruta: str
    chat_web_activo: bool
    chat_web_url: str
    checklist: list[PasoConfiguracion]


@router.get("/estado", response_model=EstadoBot)
def estado_del_bot(db: Session = Depends(get_db)) -> EstadoBot:
    s = get_settings()
    config = bot_config.obtener_config(db)
    cliente_ia = ClienteIA(s)
    ia_configurada = cliente_ia.configurada
    n_claves = cliente_ia.claves_configuradas
    partes = []
    if n_claves:
        partes.append(f"Gemini con {n_claves} clave{'s' if n_claves != 1 else ''}")
    if cliente_ia.con_groq:
        partes.append("Groq como respaldo" if n_claves else "Groq")
    resumen_proveedores = " + ".join(partes)
    if cliente_ia.con_groq and n_claves:
        proveedor = "Google Gemini + Groq (respaldo)"
    else:
        proveedor = "Groq" if cliente_ia.con_groq else "Google Gemini"
    ia_habilitada = bot_config.es_verdadero(config, "ia_habilitada")
    credenciales = bool(s.whatsapp_phone_number_id and s.whatsapp_access_token)
    webhook = bool(s.whatsapp_webhook_verify_token and s.whatsapp_app_secret)
    plantilla_reservas = bool(s.whatsapp_template_name and s.whatsapp_notify_to)
    plantilla_confirmacion = bool(s.whatsapp_confirmation_template_name)
    plantilla_inventario = bool(s.whatsapp_inventory_template_name and (s.whatsapp_inventory_notify_to or s.whatsapp_notify_to))
    chat_activo = bot_config.es_verdadero(config, "bot_activo")
    checklist = [
        PasoConfiguracion(clave="chat", titulo="Chat web del asistente", ok=chat_activo,
                          detalle="Activo en la página pública de reservas." if chat_activo else "Está en pausa: los clientes ven un aviso."),
        PasoConfiguracion(clave="ia", titulo="IA conectada (Gemini)", ok=ia_configurada and ia_habilitada,
                          detalle=(f"Conectada: {resumen_proveedores}; el asistente entiende lenguaje natural." if ia_configurada and ia_habilitada else
                                   "Sin GEMINI_API_KEY (ni GROQ_API_KEY) el asistente funciona con su motor local de reglas." if not ia_configurada else
                                   "La IA está desactivada en la configuración.")),
        PasoConfiguracion(clave="wa_credenciales", titulo="Credenciales de WhatsApp Cloud API", ok=credenciales,
                          detalle="Phone Number ID y token configurados." if credenciales else "Faltan WHATSAPP_PHONE_NUMBER_ID o WHATSAPP_ACCESS_TOKEN."),
        PasoConfiguracion(clave="wa_webhook", titulo="Webhook de WhatsApp", ok=webhook,
                          detalle="Token de verificación y App Secret listos." if webhook else "Faltan WHATSAPP_WEBHOOK_VERIFY_TOKEN o WHATSAPP_APP_SECRET."),
        PasoConfiguracion(clave="wa_reservas", titulo="Aviso interno de nuevas reservas", ok=plantilla_reservas,
                          detalle="Plantilla y destinatario configurados." if plantilla_reservas else "Falta WHATSAPP_NOTIFY_TO o la plantilla."),
        PasoConfiguracion(clave="wa_confirmacion", titulo="Confirmación de reserva garantizada al cliente", ok=plantilla_confirmacion,
                          detalle="Plantilla de confirmación configurada." if plantilla_confirmacion else "Falta WHATSAPP_CONFIRMATION_TEMPLATE_NAME (plantilla aprobada por Meta)."),
        PasoConfiguracion(clave="wa_inventario", titulo="Aviso de inventario por WhatsApp", ok=plantilla_inventario,
                          detalle="Plantilla y destinatario configurados." if plantilla_inventario else "Opcional: las alertas de stock siempre llegan a la campana del panel."),
    ]
    return EstadoBot(
        ia_proveedor=proveedor,
        ia_configurada=ia_configurada,
        ia_habilitada=ia_habilitada,
        ia_activa=ia_configurada and ia_habilitada,
        ia_modelo=s.gemini_model,
        ia_llamadas_hoy=llamadas_ia_hoy(),
        ia_limite_diario=int(config["ia_limite_diario"]),
        whatsapp_credenciales=credenciales,
        whatsapp_webhook=webhook,
        whatsapp_plantilla_reservas=plantilla_reservas,
        whatsapp_plantilla_confirmacion=plantilla_confirmacion,
        whatsapp_plantilla_inventario=plantilla_inventario,
        whatsapp_destino_avisos=bool(s.whatsapp_notify_to),
        webhook_ruta="/webhooks/whatsapp",
        chat_web_activo=chat_activo,
        chat_web_url=f"{s.public_frontend_url.rstrip('/')}/reservas",
        checklist=checklist,
    )


class CampoConfiguracion(BaseModel):
    clave: str
    descripcion: str
    tipo: str
    defecto: str


class ConfiguracionBot(BaseModel):
    valores: dict[str, str]
    campos: list[CampoConfiguracion]


@router.get("/configuracion", response_model=ConfiguracionBot)
def obtener_configuracion(db: Session = Depends(get_db)) -> ConfiguracionBot:
    return ConfiguracionBot(
        valores=bot_config.obtener_config(db),
        campos=[CampoConfiguracion(**c) for c in bot_config.metadatos()],
    )


@router.put("/configuracion", response_model=ConfiguracionBot)
def actualizar_configuracion(
    cambios: dict[str, str | bool | int], db: Session = Depends(get_db)
) -> ConfiguracionBot:
    valores = bot_config.actualizar_config(db, cambios)
    return ConfiguracionBot(valores=valores, campos=[CampoConfiguracion(**c) for c in bot_config.metadatos()])


class PruebaEntrada(BaseModel):
    texto: str | None = Field(default=None, max_length=600)
    accion: str | None = Field(default=None, max_length=60)
    estado: dict | None = None


class PruebaRespuesta(BaseModel):
    respuesta: ChatRespuesta
    estado: dict
    intencion: str


@router.post("/probar", response_model=PruebaRespuesta)
def probar_asistente(payload: PruebaEntrada, db: Session = Depends(get_db)) -> PruebaRespuesta:
    """Conversa con el asistente en modo seguro: no crea reservas ni notificaciones."""
    if not payload.texto and not payload.accion:
        raise HTTPException(status_code=422, detail="Escribe un mensaje o elige una opción.")
    estado = _nuevo_estado(payload.estado if isinstance(payload.estado, dict) else None)
    asistente = Asistente(db, canal="web", dry_run=True, sesion_id="prueba")
    resultado = asistente.turno(estado, payload.texto, payload.accion)
    return PruebaRespuesta(
        respuesta=a_respuesta(resultado, "prueba"), estado=resultado.estado, intencion=resultado.intencion
    )


class ResultadoPrueba(BaseModel):
    ok: bool
    detalle: str
    milisegundos: int | None = None


@router.post("/ia/probar", response_model=ResultadoPrueba)
def probar_conexion_ia(db: Session = Depends(get_db)) -> ResultadoPrueba:
    config = bot_config.obtener_config(db)
    ia = ClienteIA(get_settings(), habilitada=True, limite_diario=int(config["ia_limite_diario"]))
    if not ia.configurada:
        return ResultadoPrueba(ok=False, detalle="Falta GEMINI_API_KEY en el archivo .env del backend (clave gratuita en aistudio.google.com/apikey).")
    inicio = time.perf_counter()
    try:
        ia.json(
            system="Responde únicamente con el JSON pedido.",
            mensajes=[{"role": "user", "content": "Devuelve ok=true."}],
            esquema={"type": "object", "additionalProperties": False, "required": ["ok"], "properties": {"ok": {"type": "boolean"}}},
            max_tokens=200,
        )
    except IANoDisponible as exc:
        return ResultadoPrueba(ok=False, detalle=str(exc))
    return ResultadoPrueba(ok=True, detalle=f"Conexión correcta con {ia.modelo}.", milisegundos=int((time.perf_counter() - inicio) * 1000))


class PruebaWhatsApp(BaseModel):
    telefono: str = Field(min_length=7, max_length=24, pattern=r"^[0-9+()\-\s]+$")
    texto: str | None = Field(default=None, max_length=300)


@router.post("/whatsapp/prueba", response_model=ResultadoPrueba)
def enviar_prueba_whatsapp(payload: PruebaWhatsApp) -> ResultadoPrueba:
    """Envía un mensaje real de prueba al teléfono indicado.

    Por defecto usa la plantilla aprobada (funciona siempre, el teléfono debe estar en la lista de destinatarios de
    Meta). Si se pasa ``texto``, envía un texto libre, que Meta solo entrega si ese número escribió en las últimas 24 h.
    """
    digitos = re.sub(r"\D", "", payload.telefono)
    if payload.texto:
        estado, error = responder_mensaje_bot_whatsapp(digitos, payload.texto)
        if estado == "respondido":
            return ResultadoPrueba(ok=True, detalle="Meta aceptó el mensaje.")
        return ResultadoPrueba(ok=False, detalle=error or "No se pudo enviar el mensaje.")
    estado, error = enviar_aviso_prueba(digitos)
    if estado == "enviada":
        return ResultadoPrueba(ok=True, detalle=f"Meta aceptó el aviso de prueba para …{digitos[-4:]}. Debe llegar en unos segundos.")
    return ResultadoPrueba(ok=False, detalle=error or "No se pudo enviar el aviso de prueba.")


class PasoDiagnostico(BaseModel):
    clave: str
    titulo: str
    ok: bool
    detalle: str


class ResultadoDiagnostico(BaseModel):
    ok: bool
    pasos: list[PasoDiagnostico]


@router.post("/whatsapp/diagnostico", response_model=ResultadoDiagnostico)
def diagnosticar_whatsapp() -> ResultadoDiagnostico:
    """Revisa variables, token, número y plantilla, y envía el aviso real de reserva con datos de prueba."""
    return ResultadoDiagnostico(**diagnosticar_aviso_reserva())
