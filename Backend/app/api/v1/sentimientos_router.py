from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, require_roles
from app.application import bot_config, chat_service
from app.application.chat_nlu import combinar_sentimiento, nlu_ia
from app.application.ia_client import ClienteIA, IANoDisponible
from app.application.sentiment_service import NOMBRES_ASPECTO, analizar_sentimiento
from app.core.config import get_settings
from app.domain.enums import RolUsuario
from app.infrastructure.models.chat_model import ChatMensajeModel, ChatSesionModel
from app.infrastructure.models.whatsapp_inbound_message_model import WhatsAppInboundMessageModel

router = APIRouter(
    prefix="/sentimientos",
    tags=["Análisis de sentimientos"],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)


class TextoAnalisis(BaseModel):
    texto: str = Field(min_length=3, max_length=2000)
    usar_ia: bool = False

    @field_validator("texto")
    @classmethod
    def limpiar_texto(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Escribe al menos tres caracteres.")
        return value


@router.post("/analizar")
def analizar(payload: TextoAnalisis, db: Session = Depends(get_db)) -> dict:
    # El texto se analiza en memoria y no se almacena.
    resultado = analizar_sentimiento(payload.texto)
    if not payload.usar_ia:
        return resultado
    config = bot_config.obtener_config(db)
    ia = ClienteIA(get_settings(), habilitada=bot_config.es_verdadero(config, "ia_habilitada"), limite_diario=int(config["ia_limite_diario"]))
    try:
        nlu = nlu_ia(ia, config, payload.texto, [], paso="libre", slots_actuales={}, historial=[])
    except IANoDisponible as exc:
        return {**resultado, "aviso_ia": str(exc)}
    combinado = combinar_sentimiento(resultado, nlu.sentimiento)
    combinado["metodo"] = f"IA ({ia.modelo}) con evidencia del léxico local"
    return combinado


@router.get("/whatsapp/resumen")
def resumen_whatsapp(db: Session = Depends(get_db)) -> dict[str, int]:
    filas = db.execute(
        select(WhatsAppInboundMessageModel.sentiment, func.count())
        .group_by(WhatsAppInboundMessageModel.sentiment)
    ).all()
    conteos = {etiqueta: int(cantidad) for etiqueta, cantidad in filas}
    positivos = conteos.get("positivo", 0)
    neutrales = conteos.get("neutral", 0)
    negativos = conteos.get("negativo", 0)
    return {
        "total": positivos + neutrales + negativos,
        "positivo": positivos,
        "neutral": neutrales,
        "negativo": negativos,
    }


# --- Panel analítico del asistente -------------------------------------------------------


class Totales(BaseModel):
    mensajes: int
    positivo: int
    neutral: int
    negativo: int
    promedio: float
    sesiones: int
    escaladas_abiertas: int


class PuntoTendencia(BaseModel):
    fecha: date
    positivo: int
    neutral: int
    negativo: int
    promedio: float


class AspectoPanel(BaseModel):
    aspecto: str
    nombre: str
    positivo: int
    neutral: int
    negativo: int


class EmocionPanel(BaseModel):
    emocion: str
    total: int


class PanelSentimientos(BaseModel):
    periodo_dias: int
    totales: Totales
    por_canal: dict[str, dict[str, int]]
    tendencia: list[PuntoTendencia]
    aspectos: list[AspectoPanel]
    emociones: list[EmocionPanel]


def _aware(valor: datetime) -> datetime:
    return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)


@router.get("/panel", response_model=PanelSentimientos)
def panel(dias: int = Query(default=14, ge=1, le=90), db: Session = Depends(get_db)) -> PanelSentimientos:
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    filas = db.execute(
        select(
            ChatMensajeModel.sentimiento, ChatMensajeModel.puntaje, ChatMensajeModel.emocion,
            ChatMensajeModel.aspectos, ChatMensajeModel.creado_en, ChatSesionModel.canal,
        )
        .join(ChatSesionModel, ChatSesionModel.id == ChatMensajeModel.sesion_id)
        .where(ChatMensajeModel.autor == "usuario", ChatMensajeModel.creado_en >= desde)
    ).all()

    conteo = Counter()
    suma = 0.0
    por_canal: dict[str, Counter] = defaultdict(Counter)
    por_dia: dict[date, list[tuple[str, float]]] = defaultdict(list)
    aspectos: dict[str, Counter] = defaultdict(Counter)
    emociones: Counter = Counter()
    for sentimiento, puntaje, emocion, asp, creado, canal in filas:
        etiqueta = sentimiento or "neutral"
        valor = float(puntaje or 0)
        conteo[etiqueta] += 1
        suma += valor
        por_canal[canal][etiqueta] += 1
        por_canal[canal]["total"] += 1
        por_dia[_aware(creado).date()].append((etiqueta, valor))
        if emocion:
            emociones[emocion] += 1
        for par in (asp or "").split(","):
            if ":" in par:
                clave, sent = par.split(":", 1)
                aspectos[clave][sent] += 1

    total = sum(conteo.values())
    hoy = datetime.now(timezone.utc).date()
    tendencia = []
    for i in range(dias - 1, -1, -1):
        dia = hoy - timedelta(days=i)
        registros = por_dia.get(dia, [])
        c = Counter(e for e, _ in registros)
        tendencia.append(PuntoTendencia(
            fecha=dia, positivo=c["positivo"], neutral=c["neutral"], negativo=c["negativo"],
            promedio=round(sum(v for _, v in registros) / len(registros), 2) if registros else 0.0,
        ))

    sesiones = int(db.execute(select(func.count()).select_from(ChatSesionModel).where(ChatSesionModel.creada_en >= desde)).scalar_one())
    abiertas = int(db.execute(
        select(func.count()).select_from(ChatSesionModel).where(ChatSesionModel.escalada.is_(True), ChatSesionModel.escalada_resuelta.is_(False))
    ).scalar_one())

    return PanelSentimientos(
        periodo_dias=dias,
        totales=Totales(
            mensajes=total, positivo=conteo["positivo"], neutral=conteo["neutral"], negativo=conteo["negativo"],
            promedio=(round(suma / total, 2) + 0.0) if total else 0.0, sesiones=sesiones, escaladas_abiertas=abiertas,
        ),
        por_canal={canal: dict(c) for canal, c in por_canal.items()},
        tendencia=tendencia,
        aspectos=[
            AspectoPanel(aspecto=a, nombre=NOMBRES_ASPECTO.get(a, a), positivo=c["positivo"], neutral=c["neutral"], negativo=c["negativo"])
            for a, c in sorted(aspectos.items(), key=lambda par: -sum(par[1].values()))
        ],
        emociones=[EmocionPanel(emocion=e, total=n) for e, n in emociones.most_common()],
    )


# --- Conversaciones ---------------------------------------------------------------------


class ConversacionResumen(BaseModel):
    id: str
    canal: str
    mensajes_total: int
    negativos: int
    promedio: float
    escalada: bool
    escalada_resuelta: bool
    creada_en: datetime
    actualizada_en: datetime
    con_texto: bool
    dejo_contacto: bool
    reserva_id: int | None


class MensajeConversacion(BaseModel):
    autor: str
    texto: str | None
    sentimiento: str | None
    puntaje: float | None
    emocion: str | None
    aspectos: list[str]
    intencion: str | None
    creado_en: datetime


class ConversacionDetalle(ConversacionResumen):
    mensajes: list[MensajeConversacion]
    contacto_humano: str | None


def _resumen(sesion: ChatSesionModel) -> ConversacionResumen:
    estado = chat_service.estado_de(sesion)
    return ConversacionResumen(
        id=sesion.id, canal=sesion.canal, mensajes_total=sesion.mensajes_total or 0,
        negativos=sesion.negativos or 0, promedio=float(sesion.sentimiento_promedio or 0),
        escalada=bool(sesion.escalada), escalada_resuelta=bool(sesion.escalada_resuelta),
        creada_en=sesion.creada_en, actualizada_en=sesion.actualizada_en,
        con_texto=sesion.canal == "web", dejo_contacto=bool(estado.get("contacto_humano")),
        reserva_id=sesion.reserva_id,
    )


@router.get("/conversaciones", response_model=list[ConversacionResumen])
def listar_conversaciones(
    estado: Literal["escaladas", "abiertas", "todas"] = "todas",
    canal: Literal["web", "whatsapp"] | None = None,
    limite: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[ConversacionResumen]:
    stmt = select(ChatSesionModel).order_by(ChatSesionModel.actualizada_en.desc()).limit(limite)
    if estado == "escaladas":
        stmt = stmt.where(ChatSesionModel.escalada.is_(True))
    elif estado == "abiertas":
        stmt = stmt.where(ChatSesionModel.escalada.is_(True), ChatSesionModel.escalada_resuelta.is_(False))
    if canal:
        stmt = stmt.where(ChatSesionModel.canal == canal)
    return [_resumen(s) for s in db.execute(stmt).scalars()]


@router.get("/conversaciones/{sesion_id}", response_model=ConversacionDetalle)
def detalle_conversacion(sesion_id: str, db: Session = Depends(get_db)) -> ConversacionDetalle:
    sesion = db.get(ChatSesionModel, sesion_id)
    if sesion is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    mensajes = db.execute(
        select(ChatMensajeModel).where(ChatMensajeModel.sesion_id == sesion_id).order_by(ChatMensajeModel.id.asc()).limit(500)
    ).scalars()
    estado = chat_service.estado_de(sesion)
    return ConversacionDetalle(
        **_resumen(sesion).model_dump(),
        mensajes=[
            MensajeConversacion(
                autor=m.autor, texto=m.texto, sentimiento=m.sentimiento,
                puntaje=float(m.puntaje) if m.puntaje is not None else None,
                emocion=m.emocion, aspectos=[a for a in (m.aspectos or "").split(",") if a],
                intencion=m.intencion, creado_en=m.creado_en,
            )
            for m in mensajes
        ],
        contacto_humano=estado.get("contacto_humano") if sesion.canal == "web" else None,
    )


@router.post("/conversaciones/{sesion_id}/resolver", response_model=ConversacionResumen)
def resolver_conversacion(sesion_id: str, db: Session = Depends(get_db)) -> ConversacionResumen:
    sesion = db.get(ChatSesionModel, sesion_id)
    if sesion is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    sesion.escalada_resuelta = True
    db.commit()
    db.refresh(sesion)
    return _resumen(sesion)
