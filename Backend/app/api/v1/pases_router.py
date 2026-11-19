"""Pase de ingreso público: el invitado (o su promotor) abre su QR desde un enlace.

El código del pase actúa como secreto de acceso a su propia información; por eso estas
rutas no requieren sesión, pero nunca exponen datos de otros invitados ni del equipo.
"""

from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, require_roles
from app.application.qr_format import (
    DESCRIPCION_FORMATOS,
    FORMATOS_ESCRITURA,
    construir_payload_qr,
    leer_qr,
)
from app.application.qr_render import renderizar_qr
from app.core.config import get_settings
from app.domain.enums import RolUsuario
from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.invitado_model import InvitadoModel
from app.infrastructure.models.reserva_model import ReservaModel
from sqlalchemy import select

router = APIRouter(tags=["Pases y formatos QR"])

FormatoPayload = Literal["codigo", "url", "esquema", "json", "base64"]


class PaseReserva(BaseModel):
    reserva_id: int
    codigo_garantia: str | None
    tipo: str
    ubicacion_asignada: str | None
    hora_limite: str | None


class PasePublico(BaseModel):
    codigo: str
    nombre: str
    estado: str
    valido: bool
    evento_nombre: str
    evento_fecha: date
    evento_tematica: str | None
    flyer_url: str | None
    reserva: PaseReserva | None


class FormatoQrInfo(BaseModel):
    formato: str
    descripcion: str


class LecturaQr(BaseModel):
    contenido: str


class LecturaQrRespuesta(BaseModel):
    codigo: str
    formato: str


def _cargar_pase(db: Session, codigo: str) -> tuple[InvitadoModel, EventoModel]:
    try:
        codigo = leer_qr(codigo).codigo
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Pase no encontrado.") from exc
    invitado = db.execute(select(InvitadoModel).where(InvitadoModel.qr_code == codigo)).scalar_one_or_none()
    if invitado is None:
        raise HTTPException(status_code=404, detail="Pase no encontrado.")
    evento = db.get(EventoModel, invitado.evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Pase no encontrado.")
    return invitado, evento


@router.get("/qr/formatos", response_model=list[FormatoQrInfo])
def formatos_qr_soportados() -> list[FormatoQrInfo]:
    return [FormatoQrInfo(formato=f, descripcion=DESCRIPCION_FORMATOS[f]) for f in FORMATOS_ESCRITURA]


@router.post(
    "/qr/leer",
    response_model=LecturaQrRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR, RolUsuario.PUERTA))],
)
def interpretar_contenido_qr(payload: LecturaQr) -> LecturaQrRespuesta:
    """Indica qué código y formato se detectó en un QR (útil para diagnóstico en puerta)."""
    try:
        lectura = leer_qr(payload.contenido)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return LecturaQrRespuesta(codigo=lectura.codigo, formato=lectura.formato)


@router.get("/pases/{codigo}", response_model=PasePublico)
def obtener_pase(codigo: str, db: Session = Depends(get_db)) -> PasePublico:
    invitado, evento = _cargar_pase(db, codigo)
    reserva = db.get(ReservaModel, invitado.reserva_id) if invitado.reserva_id else None
    return PasePublico(
        codigo=invitado.qr_code,
        nombre=invitado.nombre,
        estado=invitado.estado,
        valido=invitado.estado == "pendiente" and evento.estado != "cerrado",
        evento_nombre=evento.nombre,
        evento_fecha=evento.fecha,
        evento_tematica=evento.tematica,
        flyer_url=evento.flyer_url,
        reserva=PaseReserva(
            reserva_id=reserva.id,
            codigo_garantia=reserva.codigo_garantia,
            tipo=reserva.tipo,
            ubicacion_asignada=reserva.ubicacion_asignada,
            hora_limite=reserva.hora_limite,
        )
        if reserva is not None
        else None,
    )


@router.get("/pases/{codigo}/qr.{extension}")
def imagen_qr_pase(
    codigo: str,
    extension: Literal["svg", "png"],
    formato: FormatoPayload = Query(default="codigo"),
    escala: int = Query(default=10, ge=2, le=30),
    descargar: bool = False,
    db: Session = Depends(get_db),
) -> Response:
    invitado, evento = _cargar_pase(db, codigo)
    payload = construir_payload_qr(
        invitado.qr_code,
        formato,
        base_url=get_settings().public_frontend_url,
        evento_id=evento.id,
    )
    contenido, media_type = renderizar_qr(payload, extension, escala=escala)
    cabeceras = {"Cache-Control": "private, max-age=300"}
    if descargar:
        cabeceras["Content-Disposition"] = f'attachment; filename="pase-{invitado.id}-{formato}.{extension}"'
    return Response(content=contenido, media_type=media_type, headers=cabeceras)


def _escapar_ics(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@router.get("/pases/{codigo}/calendario.ics")
def calendario_pase(codigo: str, db: Session = Depends(get_db)) -> Response:
    invitado, evento = _cargar_pase(db, codigo)
    reserva = db.get(ReservaModel, invitado.reserva_id) if invitado.reserva_id else None
    inicio = evento.fecha.strftime("%Y%m%d")
    fin = date.fromordinal(evento.fecha.toordinal() + 1).strftime("%Y%m%d")
    descripcion = [f"Pase para {invitado.nombre}. Presenta el QR en la entrada."]
    if reserva is not None:
        if reserva.ubicacion_asignada:
            descripcion.append(f"Ubicación: {reserva.ubicacion_asignada}.")
        if reserva.hora_limite:
            descripcion.append(f"Llega antes de las {reserva.hora_limite}.")
        if reserva.codigo_garantia:
            descripcion.append(f"Reserva garantizada {reserva.codigo_garantia}.")
    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lineas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Medallo Club//Pases//ES",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:pase-{invitado.id}@medallo-club",
        f"DTSTAMP:{sello}",
        f"DTSTART;VALUE=DATE:{inicio}",
        f"DTEND;VALUE=DATE:{fin}",
        f"SUMMARY:{_escapar_ics(evento.nombre + ' · Medallo Club')}",
        f"DESCRIPTION:{_escapar_ics(' '.join(descripcion))}",
        "LOCATION:Medallo Club\\, Provenza\\, Medellín",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return Response(
        content="\r\n".join(lineas) + "\r\n",
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="medallo-club-{evento.id}.ics"'},
    )
