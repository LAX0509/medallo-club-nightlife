"""Asistente conversacional de Medallo Club (web y WhatsApp).

Arquitectura: *la IA propone, el sistema dispone*.
* ``chat_nlu`` entiende el mensaje (con Gemini si está disponible, con reglas si no).
* Este módulo es el gestor de diálogo determinista: valida cada dato, guía el flujo de
  reserva paso a paso, responde preguntas frecuentes con los datos oficiales del club y
  decide cuándo escalar a una persona según el análisis de sentimiento.
* Las acciones con efectos (crear/cancelar reservas, notificar) solo ocurren aquí, tras
  validar y, en el caso de la reserva, tras la confirmación explícita del cliente.
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application import bot_config, notificacion_service, reserva_service
from app.application.chat_nlu import (
    NLU,
    SlotsDetectados,
    combinar_sentimiento,
    extraer_telefono,
    fecha_larga,
    nlu_ia,
    nlu_local,
)
from app.application.ia_client import ClienteIA, IANoDisponible
from app.application.sentiment_service import analizar_sentimiento
from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.reserva_model import ReservaModel

logger = logging.getLogger(__name__)

PASOS_FLUJO = ("evento", "tipo", "asistentes", "nombre", "telefono", "notas", "confirmar")
_EMPATIA_RESERVA = re.compile(r"reserv|mesa|palco|confirm", re.IGNORECASE)


@dataclass
class Opcion:
    label: str
    valor: str


@dataclass
class TarjetaEvento:
    id: int
    nombre: str
    fecha: str
    fecha_texto: str
    tematica: str | None
    flyer_url: str | None


@dataclass
class MensajeBot:
    texto: str
    opciones: list[Opcion] = field(default_factory=list)
    eventos: list[TarjetaEvento] = field(default_factory=list)


@dataclass
class ReservaInfo:
    id: int
    token_cancelacion: str | None
    estado: str
    evento_nombre: str
    simulada: bool = False
    datos_notificacion: dict[str, Any] | None = None


@dataclass
class ResultadoTurno:
    mensajes: list[MensajeBot]
    analisis: dict[str, Any]
    intencion: str
    estado: dict[str, Any]
    ia_usada: bool
    escalada: bool = False
    escalada_nueva: bool = False
    reserva: ReservaInfo | None = None


def estado_inicial() -> dict[str, Any]:
    return {
        "paso": "libre",
        "slots": {},
        "opciones": [],
        "negativos_seguidos": 0,
        "reserva_id": None,
        "promotor_id": None,
        "escalada": False,
        "esperando_contacto": False,
        "contacto_humano": None,
        "pendiente_cancelar": None,
    }


def _nuevo_estado(estado: dict[str, Any] | None) -> dict[str, Any]:
    base = estado_inicial()
    if estado:
        base.update(copy.deepcopy(estado))
    return base


class Asistente:
    def __init__(
        self,
        db: Session,
        *,
        canal: str,
        config: dict[str, str] | None = None,
        ia: ClienteIA | None = None,
        contacto_tel: str | None = None,
        url_reservas: str | None = None,
        dry_run: bool = False,
        sesion_id: str | None = None,
    ) -> None:
        self.db = db
        self.canal = canal
        self.config = config if config is not None else bot_config.obtener_config(db)
        settings = get_settings()
        self.ia = ia or ClienteIA(
            settings,
            habilitada=bot_config.es_verdadero(self.config, "ia_habilitada"),
            limite_diario=int(self.config.get("ia_limite_diario", "1000")),
        )
        self.contacto_tel = contacto_tel
        self.url_reservas = (url_reservas or f"{settings.public_frontend_url.rstrip('/')}/reservas").strip()
        self.base_publica = settings.public_frontend_url.rstrip("/")
        self.dry_run = dry_run
        self.sesion_id = sesion_id
        self._eventos_cache: list[dict[str, Any]] | None = None

    # ------------------------------------------------------------------ datos de apoyo ---

    def eventos(self) -> list[dict[str, Any]]:
        if self._eventos_cache is None:
            filas = self.db.execute(
                select(EventoModel)
                .where(EventoModel.estado == "planeado", EventoModel.fecha >= date.today())
                .order_by(EventoModel.fecha.asc())
                .limit(6)
            ).scalars()
            self._eventos_cache = [
                {"id": e.id, "nombre": e.nombre, "fecha": e.fecha, "tematica": e.tematica, "flyer_url": e.flyer_url}
                for e in filas
            ]
        return self._eventos_cache

    def _tarjetas(self) -> list[TarjetaEvento]:
        return [
            TarjetaEvento(
                id=e["id"], nombre=e["nombre"], fecha=e["fecha"].isoformat(),
                fecha_texto=fecha_larga(e["fecha"]), tematica=e["tematica"], flyer_url=e["flyer_url"],
            )
            for e in self.eventos()
        ]

    def _evento(self, evento_id: int | None) -> dict[str, Any] | None:
        return next((e for e in self.eventos() if e["id"] == evento_id), None)

    def _menu_principal(self) -> list[Opcion]:
        return [
            Opcion("Ver eventos", "ver_eventos"),
            Opcion("Reservar mesa o palco", "reservar"),
            Opcion("Horario y ubicación", "faq:horario"),
            Opcion("Hablar con el equipo", "humano"),
        ]

    # ------------------------------------------------------------------ comprensión ------

    def _comprender(
        self, texto: str, estado: dict[str, Any], historial: list[tuple[str, str]]
    ) -> NLU:
        paso = estado["paso"]
        local = nlu_local(texto, self.eventos(), paso=paso)
        if not self.ia.disponible or self._basta_el_motor_local(local, paso):
            return local
        try:
            ia = nlu_ia(
                self.ia, self.config, texto, self.eventos(),
                paso=paso, slots_actuales=estado["slots"], historial=historial,
            )
        except IANoDisponible:
            return local
        # Los datos estructurados vienen de la IA; si dejó vacío algo que las reglas sí
        # detectaron con certeza (teléfono, número de personas), se conserva.
        for campo in ("telefono", "asistentes", "tipo"):
            if getattr(ia.slots, campo) is None and getattr(local.slots, campo) is not None:
                setattr(ia.slots, campo, getattr(local.slots, campo))
        if ia.intencion == "otro" and local.intencion not in ("otro", "queja_o_comentario"):
            ia.intencion = local.intencion  # las reglas son más fiables para intenciones concretas
        if paso == "notas" and not ia.slots.notas:
            ia.slots.notas = local.slots.notas
        ia.sentimiento = combinar_sentimiento(local.sentimiento, ia.sentimiento)
        return ia

    @staticmethod
    def _basta_el_motor_local(local: NLU, paso: str) -> bool:
        """Ahorra consultas a la IA (cuota gratuita): en un paso guiado donde las reglas ya extrajeron
        justo el dato pedido, y el tono no es negativo, no hace falta preguntarle al modelo."""
        s = local.sentimiento or {}
        if s.get("etiqueta") == "negativo" or s.get("urgente"):
            return False  # los matices y el escalamiento sí merecen a la IA
        esperado = {
            "evento": local.slots.evento_id,
            "tipo": local.slots.tipo,
            "asistentes": local.slots.asistentes,
            "nombre": local.slots.nombre,
            "telefono": local.slots.telefono,
        }
        if paso in esperado:
            return esperado[paso] is not None and local.intencion not in ("hablar_humano", "cancelar_reserva")
        if paso == "notas":
            return local.intencion not in ("hablar_humano", "cancelar_reserva")
        if paso == "confirmar":
            return local.intencion in ("afirmar", "negar")
        return False

    def _nlu_de_accion(self, accion: str) -> NLU:
        neutro = analizar_sentimiento("ok")
        neutro.update({"etiqueta": "neutral", "puntaje": 0.0, "emocion": "neutral", "aspectos": [], "urgente": False})
        nlu = NLU(intencion="otro", sentimiento=neutro)
        clave, _, valor = accion.partition(":")
        if clave == "evento" and valor.isdigit():
            nlu.slots.evento_id = int(valor)
        elif clave == "tipo" and valor in ("mesa", "palco"):
            nlu.slots.tipo = valor
        elif clave == "asistentes" and valor.isdigit():
            nlu.slots.asistentes = int(valor)
        elif clave == "notas" and valor == "ninguna":
            nlu.slots.notas = ""
        nlu.intencion = {
            "inicio": "saludo", "reservar": "reservar", "ver_eventos": "ver_eventos", "humano": "hablar_humano",
            "estado_reserva": "estado_reserva", "cancelar_pregunta": "cancelar_reserva",
            "confirmar": "afirmar", "faq": f"faq_{valor}" if valor else "otro",
        }.get(clave, "otro")
        return nlu

    def _resolver_numero(self, texto: str, estado: dict[str, Any]) -> str | None:
        """En WhatsApp las opciones se eligen escribiendo su número."""
        texto = texto.strip()
        # En "asistentes" un número es el dato pedido (personas), no una opción del menú.
        if not texto.isdigit() or not estado["opciones"] or estado["paso"] == "asistentes":
            return None
        indice = int(texto) - 1
        if 0 <= indice < len(estado["opciones"]):
            return estado["opciones"][indice]["valor"]
        return None

    # ------------------------------------------------------------------ turno ------------

    def turno(
        self,
        estado_previo: dict[str, Any] | None,
        texto: str | None,
        accion: str | None = None,
        *,
        historial: list[tuple[str, str]] | None = None,
    ) -> ResultadoTurno:
        estado = _nuevo_estado(estado_previo)
        historial = historial or []

        if not accion and texto:
            numero = self._resolver_numero(texto, estado)
            if numero:
                accion = numero

        if accion:
            nlu = self._nlu_de_accion(accion)
            texto_efectivo = ""
        else:
            nlu = self._comprender(texto or "", estado, historial)
            texto_efectivo = texto or ""

        analisis = nlu.sentimiento
        etiqueta = analisis.get("etiqueta", "neutral")
        estado["negativos_seguidos"] = estado["negativos_seguidos"] + 1 if etiqueta == "negativo" else 0

        mensajes: list[MensajeBot] = []
        reserva_info: ReservaInfo | None = None
        escalada_nueva = self._evaluar_escalamiento(nlu, estado, mensajes, texto_efectivo)

        if estado.get("esperando_contacto") and not accion:
            telefono = extraer_telefono(texto_efectivo)
            if telefono:
                estado["contacto_humano"] = telefono
                estado["esperando_contacto"] = False
                mensajes.append(MensajeBot("Gracias. Dejé tu número al equipo para que te contacte lo antes posible."))
                self._avisar_contacto(estado)
                return self._cerrar(estado, mensajes, analisis, nlu, escalada_nueva, reserva_info)

        self._despachar(nlu, estado, mensajes, texto_efectivo, accion)

        reserva_info = estado.pop("_reserva_creada", None)
        return self._cerrar(estado, mensajes, analisis, nlu, escalada_nueva, reserva_info)

    def _cerrar(
        self,
        estado: dict[str, Any],
        mensajes: list[MensajeBot],
        analisis: dict[str, Any],
        nlu: NLU,
        escalada_nueva: bool,
        reserva: ReservaInfo | None,
    ) -> ResultadoTurno:
        estado.pop("_ya_empatizo", None)
        if not mensajes:
            mensajes.append(self._mensaje_ayuda())
        ultimo_con_opciones = next((m for m in reversed(mensajes) if m.opciones), None)
        estado["opciones"] = [{"label": o.label, "valor": o.valor} for o in ultimo_con_opciones.opciones] if ultimo_con_opciones else []
        return ResultadoTurno(
            mensajes=mensajes,
            analisis=analisis,
            intencion=nlu.intencion,
            estado=estado,
            ia_usada=nlu.ia,
            escalada=bool(estado.get("escalada")),
            escalada_nueva=escalada_nueva,
            reserva=reserva,
        )

    # ------------------------------------------------------------------ escalamiento -----

    def _evaluar_escalamiento(
        self, nlu: NLU, estado: dict[str, Any], mensajes: list[MensajeBot], texto: str
    ) -> bool:
        a = nlu.sentimiento
        pide_humano = nlu.intencion == "hablar_humano"
        activo = bot_config.es_verdadero(self.config, "escalar_negativos")
        grave = bool(a.get("urgente")) or (
            a.get("etiqueta") == "negativo" and (a.get("intensidad") == "alta" or estado["negativos_seguidos"] >= 2)
        )
        if not (pide_humano or (activo and grave)):
            return False
        ya_escalada = bool(estado.get("escalada"))
        estado["escalada"] = True
        if ya_escalada and not a.get("urgente"):
            return False

        if pide_humano:
            texto_bot = "Claro, aviso al equipo para que una persona te atienda."
            nivel, titulo = "alerta", "Un cliente pide hablar con una persona"
        elif a.get("urgente"):
            texto_bot = (
                "Lamentamos muchísimo lo ocurrido y lo tomamos con total seriedad. "
                "Avisé de inmediato al equipo para que te contacte."
            )
            nivel, titulo = "critica", "Caso urgente en el asistente"
        else:
            texto_bot = "Lamentamos que algo no haya salido bien. Ya avisé al equipo para que lo revise."
            nivel, titulo = "alerta", "Cliente molesto en el asistente"
        contacto = self.config.get("contacto_equipo", "").strip()
        if contacto:
            texto_bot += f" También puedes escribirles directamente: {contacto}."
        elif self.canal == "web" and not estado.get("contacto_humano"):
            texto_bot += " Si quieres que te contacten, déjame tu WhatsApp o teléfono."
            estado["esperando_contacto"] = True
        if (
            _EMPATIA_RESERVA.search(texto)
            and self.url_reservas
            and self.canal == "whatsapp"
            and not pide_humano
        ):
            texto_bot += f" Puedes gestionar una reserva aquí: {self.url_reservas}"
        mensajes.append(MensajeBot(texto_bot))
        estado["_ya_empatizo"] = True

        if not self.dry_run:
            aspectos = ", ".join(x["aspecto"] for x in a.get("aspectos", []) if x.get("sentimiento") == "negativo")
            detalle = f"Emoción: {a.get('emocion', 'n/d')}"
            if aspectos:
                detalle += f" · Temas: {aspectos}"
            if a.get("motivo_urgencia"):
                detalle += f" · Motivo: {a['motivo_urgencia']}"
            notificacion_service.notificar(
                self.db,
                tipo="sentimiento_negativo",
                titulo=titulo,
                mensaje=f"Canal {self.canal}. {detalle}.",
                nivel=nivel,
                enlace=f"/sentimientos?sesion={self.sesion_id}" if self.sesion_id else "/sentimientos",
                referencia=f"chat:{self.sesion_id}" if self.sesion_id else None,
                deduplicar=bool(self.sesion_id) and not a.get("urgente"),
            )
        return True

    def _avisar_contacto(self, estado: dict[str, Any]) -> None:
        if self.dry_run:
            return
        notificacion_service.notificar(
            self.db,
            tipo="sentimiento_contacto",
            titulo="Un cliente dejó su contacto",
            mensaje="Alguien que expresó una molestia dejó su número para que lo contacten.",
            nivel="alerta",
            enlace=f"/sentimientos?sesion={self.sesion_id}" if self.sesion_id else "/sentimientos",
        )

    # ------------------------------------------------------------------ despacho ---------

    def _despachar(
        self, nlu: NLU, estado: dict[str, Any], mensajes: list[MensajeBot], texto: str, accion: str | None
    ) -> None:
        intencion = nlu.intencion
        en_flujo = estado["paso"] in PASOS_FLUJO
        s = nlu.slots

        if accion and accion.startswith("cambiar"):
            self._cambiar(estado, mensajes, accion.partition(":")[2])
            return
        if accion and accion.startswith("cancelar_si:"):
            self._cancelar_reserva(estado, mensajes, int(accion.partition(":")[2] or 0), confirmado=True)
            return
        if accion == "cancelar_no":
            estado["pendiente_cancelar"] = None
            mensajes.append(MensajeBot("Perfecto, tu reserva sigue como estaba.", self._menu_principal()))
            return
        if accion == "reenviar_enlace":
            self._reenviar_enlace(estado, mensajes)
            return
        if accion == "reiniciar":
            estado.update({"paso": "libre", "slots": {}})
            mensajes.append(MensajeBot("Listo, empezamos de nuevo.", self._menu_principal()))
            return

        # Respuestas del flujo de reserva (el dato esperado manda sobre la intención).
        if en_flujo:
            if intencion == "afirmar" and estado["paso"] == "confirmar":
                self._crear_reserva(estado, mensajes)
                return
            if intencion == "negar" and estado["paso"] == "confirmar":
                self._cambiar(estado, mensajes, "")
                return
            if intencion == "negar" and estado["paso"] == "notas":
                estado["slots"]["notas"] = ""
                self._avanzar(estado, mensajes)
                return
            es_pregunta_ajena = intencion.startswith("faq_") or intencion in ("ver_eventos", "estado_reserva", "cancelar_reserva")
            aporta = any(v is not None for v in (s.evento_id, s.tipo, s.asistentes, s.nombre, s.telefono)) or (
                estado["paso"] == "notas" and s.notas is not None
            )
            if aporta and not es_pregunta_ajena:
                self._aplicar_slots(estado, s)
                self._avanzar(estado, mensajes)
                return
            if es_pregunta_ajena:
                self._responder_intencion(nlu, estado, mensajes, texto)
                self._pregunta_pendiente(estado, mensajes, prefijo="Sigamos con tu reserva. ")
                return
            if intencion == "hablar_humano" or estado.pop("_ya_empatizo", False):
                return  # el escalamiento ya respondió
            if intencion == "reservar":
                self._pregunta_pendiente(estado, mensajes)
                return
            mensajes.append(MensajeBot("No logré entender ese dato. Veamos de nuevo."))
            self._pregunta_pendiente(estado, mensajes)
            return

        # Fuera del flujo.
        if intencion == "reservar" or (s.tipo and s.asistentes) or (s.evento_id and s.tipo):
            estado["paso"] = "evento"
            self._aplicar_slots(estado, s)
            self._avanzar(estado, mensajes, inicio=True)
            return
        self._responder_intencion(nlu, estado, mensajes, texto)

    # ------------------------------------------------------------------ flujo de reserva -

    def _aplicar_slots(self, estado: dict[str, Any], s: SlotsDetectados) -> None:
        slots = estado["slots"]
        if s.evento_id is not None:
            ev = self._evento(s.evento_id)
            if ev:
                slots.update(evento_id=ev["id"], evento_nombre=ev["nombre"], evento_fecha=ev["fecha"].isoformat())
        if s.tipo:
            slots["tipo"] = s.tipo
        if s.asistentes:
            slots["asistentes"] = s.asistentes
        if s.nombre:
            slots["nombre"] = s.nombre
        if s.telefono:
            slots["telefono"] = s.telefono
        if s.notas is not None and estado["paso"] == "notas":
            slots["notas"] = s.notas

    def _faltante(self, estado: dict[str, Any]) -> str:
        slots = estado["slots"]
        if "evento_id" not in slots:
            return "evento"
        for clave in ("tipo", "asistentes", "nombre"):
            if clave not in slots:
                return clave
        if "telefono" not in slots:
            if self.canal == "whatsapp" and self.contacto_tel:
                digitos = re.sub(r"\D", "", self.contacto_tel)
                slots["telefono"] = f"+{digitos}"
            else:
                return "telefono"
        if "notas" not in slots:
            return "notas"
        return "confirmar"

    def _avanzar(self, estado: dict[str, Any], mensajes: list[MensajeBot], *, inicio: bool = False) -> None:
        # Si hay un único evento disponible, se elige solo para ahorrar un paso.
        if "evento_id" not in estado["slots"] and len(self.eventos()) == 1:
            ev = self.eventos()[0]
            estado["slots"].update(evento_id=ev["id"], evento_nombre=ev["nombre"], evento_fecha=ev["fecha"].isoformat())
            mensajes.append(MensajeBot(f"Hay un evento disponible: {ev['nombre']} ({fecha_larga(ev['fecha'])}). Lo dejo seleccionado."))
        estado["paso"] = self._faltante(estado)
        self._pregunta_pendiente(estado, mensajes)

    def _pregunta_pendiente(self, estado: dict[str, Any], mensajes: list[MensajeBot], prefijo: str = "") -> None:
        paso = estado["paso"]
        slots = estado["slots"]
        if paso == "evento":
            if not self.eventos():
                estado.update(paso="libre", slots={})
                mensajes.append(MensajeBot(prefijo + "Por ahora no hay eventos abiertos para reservar. Escríbenos pronto o habla con el equipo.", self._menu_principal()))
                return
            mensajes.append(MensajeBot(
                prefijo + "¿A cuál evento quieres ir?",
                [Opcion(f"{e['nombre']} · {fecha_larga(e['fecha'])}", f"evento:{e['id']}") for e in self.eventos()],
                self._tarjetas(),
            ))
        elif paso == "tipo":
            mensajes.append(MensajeBot(prefijo + f"Genial, {slots.get('evento_nombre', 'ese evento')}. ¿Qué prefieres reservar?", [Opcion("Mesa", "tipo:mesa"), Opcion("Palco", "tipo:palco")]))
        elif paso == "asistentes":
            mensajes.append(MensajeBot(prefijo + "¿Para cuántas personas sería? (máximo 50)", [Opcion(str(n), f"asistentes:{n}") for n in (2, 4, 6, 8)]))
        elif paso == "nombre":
            mensajes.append(MensajeBot(prefijo + "¿A nombre de quién dejo la solicitud?"))
        elif paso == "telefono":
            mensajes.append(MensajeBot(prefijo + "¿A qué número de WhatsApp o teléfono te confirmamos?"))
        elif paso == "notas":
            mensajes.append(MensajeBot(prefijo + "¿Algo más que debamos saber? (celebración, ubicación preferida…). Escríbelo o toca «Sin notas».", [Opcion("Sin notas", "notas:ninguna")]))
        elif paso == "confirmar":
            tipo = "una mesa" if slots["tipo"] == "mesa" else "un palco"
            notas = f" Notas: {slots['notas']}." if slots.get("notas") else ""
            mensajes.append(MensajeBot(
                prefijo + (
                    f"Este es el resumen: {tipo} para {slots['asistentes']} {'persona' if int(slots['asistentes']) == 1 else 'personas'} en {slots['evento_nombre']} "
                    f"({fecha_larga(date.fromisoformat(slots['evento_fecha']))}), a nombre de {slots['nombre']}, "
                    f"contacto {slots['telefono']}.{notas} ¿Envío la solicitud?"
                ),
                [Opcion("Sí, enviar solicitud", "confirmar"), Opcion("Cambiar algo", "cambiar")],
            ))

    def _cambiar(self, estado: dict[str, Any], mensajes: list[MensajeBot], campo: str) -> None:
        mapa = {"evento": "evento", "tipo": "tipo", "personas": "asistentes", "nombre": "nombre", "telefono": "telefono"}
        if campo in mapa:
            clave = mapa[campo]
            if clave == "evento":
                for k in ("evento_id", "evento_nombre", "evento_fecha"):
                    estado["slots"].pop(k, None)
            else:
                estado["slots"].pop(clave, None)
            estado["paso"] = clave
            self._pregunta_pendiente(estado, mensajes)
            return
        mensajes.append(MensajeBot(
            "Claro, ¿qué quieres cambiar?",
            [Opcion("Evento", "cambiar:evento"), Opcion("Mesa o palco", "cambiar:tipo"), Opcion("Personas", "cambiar:personas"), Opcion("Nombre", "cambiar:nombre"), Opcion("Teléfono", "cambiar:telefono")],
        ))

    def _crear_reserva(self, estado: dict[str, Any], mensajes: list[MensajeBot]) -> None:
        slots = estado["slots"]
        if self.dry_run:
            info = ReservaInfo(id=0, token_cancelacion=None, estado="pendiente", evento_nombre=slots["evento_nombre"], simulada=True)
            mensajes.append(MensajeBot(f"(Prueba) Aquí se enviaría la solicitud de {slots['nombre']} para {slots['evento_nombre']}. No se creó ninguna reserva real.", self._menu_principal()))
            estado.update(paso="libre", slots={})
            estado["_reserva_creada"] = info
            return
        try:
            creada = reserva_service.crear_solicitud(
                self.db,
                evento_id=slots["evento_id"],
                nombre_cliente=slots["nombre"],
                telefono=slots["telefono"],
                tipo=slots["tipo"],
                asistentes=int(slots["asistentes"]),
                notas=slots.get("notas") or None,
                promotor_id=estado.get("promotor_id"),
            )
        except DomainError as exc:
            estado.update(paso="libre", slots={})
            mensajes.append(MensajeBot(f"{exc} Elige otro evento y lo intentamos de nuevo.", self._menu_principal()))
            return
        reserva = creada.reserva
        estado["reserva_id"] = reserva.id
        estado.update(paso="libre", slots={})
        enlace = f"{self.base_publica}/reservas?reserva={reserva.id}&token={creada.token_cancelacion}"
        texto = (
            f"¡Listo, {reserva.nombre_cliente}! Registré tu solicitud #{reserva.id} para "
            f"{'una mesa' if reserva.tipo == 'mesa' else 'un palco'} en {creada.evento.nombre}. "
            "Queda pendiente hasta que el equipo confirme el cupo; cuando la garantice recibirás tu código "
            "de garantía y un pase QR por persona."
        )
        if self.canal == "whatsapp":
            texto += f"\nSigue o gestiona tu reserva aquí: {enlace}"
        mensajes.append(MensajeBot(texto, [Opcion("Estado de mi reserva", "estado_reserva"), Opcion("Ver eventos", "ver_eventos")]))
        estado["_reserva_creada"] = ReservaInfo(
            id=reserva.id,
            token_cancelacion=creada.token_cancelacion,
            estado="pendiente",
            evento_nombre=creada.evento.nombre,
            datos_notificacion={
                "id": reserva.id,
                "nombre_cliente": reserva.nombre_cliente,
                "telefono": reserva.telefono,
                "evento_nombre": creada.evento.nombre,
                "tipo": "Mesa" if reserva.tipo == "mesa" else "Palco",
                "asistentes": reserva.asistentes,
                "promotor": creada.promotor.nombre if creada.promotor else "Asistente virtual",
                "notas": reserva.notas or "Sin observaciones",
            },
        )

    # ------------------------------------------------------------------ otras intenciones -

    def _mensaje_ayuda(self) -> MensajeBot:
        return MensajeBot(
            "Puedo mostrarte los próximos eventos, ayudarte a reservar una mesa o un palco y resolver dudas del club. ¿Qué necesitas?",
            self._menu_principal(),
        )

    def _responder_intencion(self, nlu: NLU, estado: dict[str, Any], mensajes: list[MensajeBot], texto: str) -> None:
        c = self.config
        intencion = nlu.intencion
        acciones_faq = [Opcion("Reservar mesa o palco", "reservar"), Opcion("Ver eventos", "ver_eventos")]
        if intencion == "saludo":
            mensajes.append(MensajeBot(nlu.respuesta or c["saludo"], self._menu_principal()))
        elif intencion == "ver_eventos":
            if not self.eventos():
                mensajes.append(MensajeBot("Por ahora no hay eventos abiertos. Vuelve pronto o escríbenos para enterarte primero.", self._menu_principal()))
            else:
                mensajes.append(MensajeBot("Estos son los próximos eventos:", [Opcion("Reservar", "reservar")], self._tarjetas()))
        elif intencion == "faq_horario":
            mensajes.append(MensajeBot(f"Nuestro horario: {c['horario']}", acciones_faq))
        elif intencion == "faq_ubicacion":
            mensajes.append(MensajeBot(f"Estamos en {c['direccion']}.", acciones_faq))
        elif intencion == "faq_precio":
            mensajes.append(MensajeBot(c["info_precios"], acciones_faq))
        elif intencion == "faq_vestimenta":
            mensajes.append(MensajeBot(f"{c['dress_code']} Ingreso desde los {c['edad_minima']} años.", acciones_faq))
        elif intencion == "faq_politica":
            mensajes.append(MensajeBot(f"{c['politica_reservas']} Edad mínima de ingreso: {c['edad_minima']} años.", acciones_faq))
        elif intencion == "estado_reserva":
            self._estado_reserva(estado, mensajes)
        elif intencion == "cancelar_reserva":
            self._cancelar_reserva(estado, mensajes, None, confirmado=False)
        elif intencion == "agradecer":
            mensajes.append(MensajeBot("¡Con gusto! Si necesitas algo más, aquí estoy.", self._menu_principal()))
        elif intencion == "despedida":
            mensajes.append(MensajeBot("¡Hasta pronto! Te esperamos en Medallo Club."))
        elif intencion == "afirmar":
            mensajes.append(MensajeBot("¡Perfecto! ¿Qué te gustaría hacer?", self._menu_principal()))
        elif intencion == "negar":
            mensajes.append(MensajeBot("Entendido. Si cambias de opinión, aquí estoy.", self._menu_principal()))
        elif intencion == "hablar_humano":
            return  # ya respondió el escalamiento
        elif intencion == "queja_o_comentario":
            if estado.pop("_ya_empatizo", False):
                return
            etiqueta = nlu.sentimiento.get("etiqueta")
            if nlu.respuesta:
                mensajes.append(MensajeBot(nlu.respuesta, self._menu_principal() if etiqueta != "negativo" else []))
            elif etiqueta == "negativo":
                mensajes.append(MensajeBot("Lamentamos que algo no haya salido bien. Registré tu mensaje para que el equipo lo revise; si quieres, cuéntame qué pasó."))
            elif etiqueta == "positivo":
                mensajes.append(MensajeBot("¡Gracias por tu comentario! Nos alegra mucho que lo hayas disfrutado.", self._menu_principal()))
            else:
                mensajes.append(MensajeBot("Gracias por escribirnos. Compartí tu comentario con el equipo.", self._menu_principal()))
        else:  # otro
            mensajes.append(MensajeBot(nlu.respuesta, self._menu_principal()) if nlu.respuesta else self._mensaje_ayuda())

    def _reservas_del_contacto(self, estado: dict[str, Any]) -> list[ReservaModel]:
        if self.canal == "whatsapp" and self.contacto_tel:
            candidatas = self.db.execute(
                select(ReservaModel).order_by(ReservaModel.id.desc()).limit(300)
            ).scalars()
            return [r for r in candidatas if reserva_service.coincide_telefono(r.telefono, self.contacto_tel)][:3]
        if estado.get("reserva_id"):
            reserva = self.db.get(ReservaModel, estado["reserva_id"])
            return [reserva] if reserva else []
        return []

    def _estado_reserva(self, estado: dict[str, Any], mensajes: list[MensajeBot]) -> None:
        reservas = [r for r in self._reservas_del_contacto(estado) if r.estado != "cancelada"] or self._reservas_del_contacto(estado)
        if not reservas:
            ayuda = (
                "No encuentro reservas asociadas a este chat. Si ya hiciste una, usa el enlace privado que recibiste al solicitarla."
                if self.canal == "web" else
                "No encuentro reservas asociadas a este número. ¿Quieres hacer una?"
            )
            mensajes.append(MensajeBot(ayuda, [Opcion("Reservar mesa o palco", "reservar")]))
            return
        lineas = []
        for r in reservas:
            evento = self.db.get(EventoModel, r.evento_id)
            nombre = evento.nombre if evento else "el evento"
            if r.estado == "confirmada" and r.codigo_garantia:
                extra = f" Hora límite {r.hora_limite}." if r.hora_limite else ""
                extra += f" Ubicación: {r.ubicacion_asignada}." if r.ubicacion_asignada else ""
                lineas.append(f"#{r.id} · {nombre}: GARANTIZADA con el código {r.codigo_garantia}.{extra}")
            elif r.estado == "confirmada":
                lineas.append(f"#{r.id} · {nombre}: confirmada.")
            elif r.estado == "cancelada":
                lineas.append(f"#{r.id} · {nombre}: cancelada.")
            else:
                lineas.append(f"#{r.id} · {nombre}: pendiente; el equipo está validando el cupo.")
        opciones = [Opcion("Cancelar mi reserva", "cancelar_pregunta")] if any(r.estado != "cancelada" for r in reservas) else []
        if self.canal == "whatsapp" and any(r.estado != "cancelada" for r in reservas):
            opciones.insert(0, Opcion("Recibir mi enlace con pases", "reenviar_enlace"))
        mensajes.append(MensajeBot("Esto es lo que veo:\n" + "\n".join(lineas), opciones))

    def _reenviar_enlace(self, estado: dict[str, Any], mensajes: list[MensajeBot]) -> None:
        reservas = [r for r in self._reservas_del_contacto(estado) if r.estado != "cancelada"]
        if self.canal != "whatsapp" or not reservas:
            mensajes.append(MensajeBot("No encuentro una reserva activa para enviarte el enlace.", self._menu_principal()))
            return
        reserva = reservas[0]
        if self.dry_run:
            mensajes.append(MensajeBot("(Prueba) Aquí se enviaría un enlace nuevo; el anterior dejaría de funcionar."))
            return
        token = reserva_service.rotar_token(self.db, reserva)
        enlace = f"{self.base_publica}/reservas?reserva={reserva.id}&token={token}"
        mensajes.append(MensajeBot(f"Este es tu enlace privado para ver tu reserva #{reserva.id} y tus pases QR (el enlace anterior dejó de funcionar):\n{enlace}"))

    def _cancelar_reserva(self, estado: dict[str, Any], mensajes: list[MensajeBot], reserva_id: int | None, *, confirmado: bool) -> None:
        reservas = [r for r in self._reservas_del_contacto(estado) if r.estado != "cancelada"]
        if not reservas:
            mensajes.append(MensajeBot("No encuentro una reserva activa que pueda cancelar desde este chat.", self._menu_principal()))
            return
        reserva = next((r for r in reservas if r.id == reserva_id), reservas[0]) if reserva_id else reservas[0]
        if not confirmado:
            mensajes.append(MensajeBot(
                f"¿Seguro que quieres cancelar la reserva #{reserva.id}?",
                [Opcion("Sí, cancelar", f"cancelar_si:{reserva.id}"), Opcion("No, conservarla", "cancelar_no")],
            ))
            return
        if self.dry_run:
            mensajes.append(MensajeBot("(Prueba) Aquí se cancelaría la reserva.", self._menu_principal()))
            return
        try:
            reserva_service.cancelar(self.db, reserva, origen="cancelada desde el asistente")
            mensajes.append(MensajeBot(f"Listo, cancelé tu reserva #{reserva.id}. Si cambias de planes, puedes pedir otra cuando quieras.", self._menu_principal()))
        except DomainError as exc:
            mensajes.append(MensajeBot(str(exc), self._menu_principal()))


# --- Render para WhatsApp ----------------------------------------------------------------


def a_texto_whatsapp(mensajes: list[MensajeBot]) -> str:
    """Convierte los mensajes del asistente a un único texto con opciones numeradas."""
    bloques: list[str] = []
    for i, m in enumerate(mensajes):
        bloque = m.texto
        if m.eventos and i == len(mensajes) - 1 and not m.opciones:
            bloque += "\n" + "\n".join(f"• {e.nombre} · {e.fecha_texto}" for e in m.eventos)
        bloques.append(bloque)
    ultimo = next((m for m in reversed(mensajes) if m.opciones), None)
    if ultimo:
        bloques.append("Responde con el número:\n" + "\n".join(f"{n}) {o.label}" for n, o in enumerate(ultimo.opciones, 1)))
    return "\n\n".join(bloques)[:4000]
