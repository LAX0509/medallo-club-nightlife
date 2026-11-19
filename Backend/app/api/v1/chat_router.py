"""Chat público del asistente de reservas (sin sesión de usuario).

La sesión se identifica con un UUID generado por el servidor: actúa como credencial de esa
conversación. Hay límite de frecuencia por IP para evitar abuso (y gasto de IA).
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db
from app.application import bot_config, chat_service
from app.application.chatbot import Asistente, MensajeBot, ResultadoTurno, estado_inicial
from app.application.ia_client import ClienteIA
from app.application.whatsapp_notification_service import notificar_nueva_reserva
from app.core.config import get_settings
from app.core.tareas import lanzar
from app.infrastructure.models.chat_model import ChatMensajeModel, ChatSesionModel
from app.schemas.chat_schema import (
    AnalisisSalida,
    ChatEntrada,
    ChatEstadoPublico,
    ChatHistorial,
    ChatHistorialItem,
    ChatRespuesta,
    MensajeSalida,
    OpcionSalida,
    ReservaChatSalida,
    TarjetaEventoSalida,
)
from sqlalchemy import select
from datetime import date

router = APIRouter(prefix="/chat", tags=["Asistente de reservas (chat)"])

LIMITE_MENSAJES_POR_MINUTO = 30
LIMITE_MENSAJES_POR_SESION = 300


class _LimitadorFrecuencia:
    def __init__(self, maximo: int, ventana: float = 60.0) -> None:
        self._maximo, self._ventana = maximo, ventana
        self._visitas: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def permitir(self, clave: str) -> bool:
        ahora = time.monotonic()
        with self._lock:
            cola = self._visitas[clave]
            while cola and ahora - cola[0] > self._ventana:
                cola.popleft()
            if len(cola) >= self._maximo:
                return False
            cola.append(ahora)
            if len(self._visitas) > 5000:  # evita crecer sin límite
                self._visitas.clear()
            return True


_limitador = _LimitadorFrecuencia(LIMITE_MENSAJES_POR_MINUTO)


def limitar_frecuencia(request: Request) -> None:
    cliente = request.client.host if request.client else "desconocido"
    if not _limitador.permitir(cliente):
        raise HTTPException(status_code=429, detail="Estás escribiendo muy rápido. Espera unos segundos.")


def a_respuesta(resultado: ResultadoTurno, sesion_id: str) -> ChatRespuesta:
    base = get_settings().public_frontend_url.rstrip("/")
    reserva = None
    if resultado.reserva is not None:
        r = resultado.reserva
        reserva = ReservaChatSalida(
            id=r.id,
            estado=r.estado,
            evento_nombre=r.evento_nombre,
            token_cancelacion=r.token_cancelacion,
            url_gestion=f"{base}/reservas?reserva={r.id}&token={r.token_cancelacion}" if r.token_cancelacion else None,
            simulada=r.simulada,
        )
    a = resultado.analisis
    return ChatRespuesta(
        sesion_id=sesion_id,
        mensajes=[
            MensajeSalida(
                texto=m.texto,
                opciones=[OpcionSalida(label=o.label, valor=o.valor) for o in m.opciones],
                eventos=[
                    TarjetaEventoSalida(
                        id=e.id, nombre=e.nombre, fecha=date.fromisoformat(e.fecha),
                        fecha_texto=e.fecha_texto, tematica=e.tematica, flyer_url=e.flyer_url,
                    )
                    for e in m.eventos
                ],
            )
            for m in resultado.mensajes
        ],
        analisis=AnalisisSalida(
            etiqueta=a.get("etiqueta", "neutral"),
            puntaje=float(a.get("puntaje", 0)),
            emocion=a.get("emocion", "neutral"),
            intensidad=a.get("intensidad", "baja"),
            aspectos=a.get("aspectos", []),
            urgente=bool(a.get("urgente")),
        ),
        ia_usada=resultado.ia_usada,
        escalada=resultado.escalada,
        reserva=reserva,
    )


@router.get("/estado", response_model=ChatEstadoPublico)
def estado_del_asistente(db: Session = Depends(get_db)) -> ChatEstadoPublico:
    config = bot_config.obtener_config(db)
    ia_activa = ClienteIA(get_settings()).configurada and bot_config.es_verdadero(config, "ia_habilitada")
    return ChatEstadoPublico(
        activo=bot_config.es_verdadero(config, "bot_activo"),
        ia=ia_activa,
        nombre_bot=config["nombre_bot"],
        saludo=config["saludo"],
    )


@router.post("/mensajes", response_model=ChatRespuesta, dependencies=[Depends(limitar_frecuencia)])
def enviar_mensaje(
    payload: ChatEntrada,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ChatRespuesta:
    config = bot_config.obtener_config(db)
    sesion = chat_service.obtener_sesion_web(db, payload.sesion_id, promotor_id=payload.promotor_id)

    if not bot_config.es_verdadero(config, "bot_activo"):
        pausa = MensajeBot("El asistente está en pausa por ahora. Puedes volver más tarde o escribirnos directamente.")
        resultado = ResultadoTurno(
            mensajes=[pausa], analisis={"etiqueta": "neutral", "puntaje": 0, "emocion": "neutral"},
            intencion="otro", estado=chat_service.estado_de(sesion) or estado_inicial(), ia_usada=False,
        )
        return a_respuesta(resultado, sesion.id)

    if (sesion.mensajes_total or 0) >= LIMITE_MENSAJES_POR_SESION:
        raise HTTPException(status_code=429, detail="Esta conversación alcanzó su límite de mensajes. Inicia una nueva.")

    asistente = Asistente(db, canal="web", config=config, sesion_id=sesion.id)
    resultado = asistente.turno(
        chat_service.estado_de(sesion),
        payload.texto,
        payload.accion,
        historial=chat_service.historial(db, sesion.id),
    )
    chat_service.guardar_turno(db, sesion, texto_usuario=payload.texto or payload.accion or "", resultado=resultado)

    if resultado.reserva and resultado.reserva.datos_notificacion:
        lanzar(background_tasks, notificar_nueva_reserva, resultado.reserva.datos_notificacion)
    return a_respuesta(resultado, sesion.id)


@router.get("/sesiones/{sesion_id}", response_model=ChatHistorial)
def historial_de_sesion(sesion_id: str, db: Session = Depends(get_db)) -> ChatHistorial:
    sesion = db.get(ChatSesionModel, sesion_id)
    if sesion is None or sesion.canal != "web":
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    filas = db.execute(
        select(ChatMensajeModel)
        .where(ChatMensajeModel.sesion_id == sesion_id, ChatMensajeModel.texto.is_not(None))
        .order_by(ChatMensajeModel.id.asc())
        .limit(200)
    ).scalars()
    estado = chat_service.estado_de(sesion)
    return ChatHistorial(
        sesion_id=sesion.id,
        mensajes=[ChatHistorialItem(autor=f.autor, texto=f.texto or "", creado_en=f.creado_en) for f in filas],
        opciones=[OpcionSalida(label=o["label"], valor=o["valor"]) for o in estado.get("opciones", [])],
        paso=estado.get("paso", "libre"),
        reserva_id=estado.get("reserva_id"),
    )
