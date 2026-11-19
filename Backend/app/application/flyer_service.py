"""Flyers de eventos (imagen o video) guardados en la base de datos.

El hosting sin servidor (Vercel) no permite escribir en disco y limita cada solicitud y cada respuesta a
unos 4,5 MB. Por eso el archivo se recibe y se guarda en trozos, y se entrega con soporte de ``Range``
(los navegadores piden los videos por rangos).
"""
import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.models.evento_flyer_model import EventoFlyerModel, EventoFlyerParteModel
from app.infrastructure.models.evento_model import EventoModel

MAX_IMAGEN_BYTES = 4 * 1024 * 1024
MAX_VIDEO_BYTES = 20 * 1024 * 1024
MAX_PARTE_BYTES = 3_700_000
MAX_PARTES = 8
MAX_RESPUESTA_BYTES = 4 * 1024 * 1024
FLYER_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
}
_SUBIDA = re.compile(r"^[0-9a-fA-F-]{8,36}$")
_UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "flyers"


class FlyerError(Exception):
    def __init__(self, codigo: int, detalle: str) -> None:
        super().__init__(detalle)
        self.codigo = codigo
        self.detalle = detalle


def limite_para(tipo: str) -> int:
    return MAX_VIDEO_BYTES if tipo.startswith("video/") else MAX_IMAGEN_BYTES


def cabecera_valida(tipo: str, cabecera: bytes) -> bool:
    return (
        (tipo == "image/jpeg" and cabecera.startswith(b"\xff\xd8\xff"))
        or (tipo == "image/png" and cabecera.startswith(b"\x89PNG\r\n\x1a\n"))
        or (tipo == "image/webp" and cabecera.startswith(b"RIFF") and cabecera[8:12] == b"WEBP")
        or (tipo == "image/gif" and cabecera.startswith((b"GIF87a", b"GIF89a")))
        or (tipo == "video/mp4" and len(cabecera) > 8 and cabecera[4:8] == b"ftyp")
        or (tipo == "video/webm" and cabecera.startswith(b"\x1a\x45\xdf\xa3"))
    )


def _url(evento_id: int, subida: str, tipo: str) -> str:
    return f"{get_settings().api_v1_prefix}/eventos/{evento_id}/flyer/{subida.replace('-', '').lower()}{FLYER_TYPES[tipo]}"


def _borrar_archivo_en_disco(flyer_url: str | None) -> None:
    """Flyers antiguos (de cuando se guardaban en disco, o los de demostración): se borran si existen."""
    if not flyer_url or "/uploads/flyers/" not in flyer_url:
        return
    try:
        archivo = _UPLOADS_DIR / Path(flyer_url).name
        if archivo.parent == _UPLOADS_DIR and archivo.exists():
            archivo.unlink()
    except OSError:
        pass


def quitar(db: Session, evento: EventoModel, *, confirmar: bool = True) -> None:
    db.execute(delete(EventoFlyerParteModel).where(EventoFlyerParteModel.evento_id == evento.id))
    db.execute(delete(EventoFlyerModel).where(EventoFlyerModel.evento_id == evento.id))
    _borrar_archivo_en_disco(evento.flyer_url)
    evento.flyer_url = None
    if confirmar:
        db.commit()


def _finalizar(db: Session, evento: EventoModel, subida: str, tipo: str, tamano: int) -> None:
    anterior = evento.flyer_url
    db.execute(
        delete(EventoFlyerParteModel).where(
            EventoFlyerParteModel.evento_id == evento.id, EventoFlyerParteModel.subida != subida
        )
    )
    meta = db.get(EventoFlyerModel, evento.id)
    if meta is None:
        db.add(EventoFlyerModel(evento_id=evento.id, subida=subida, tipo=tipo, tamano=tamano))
    else:
        meta.subida, meta.tipo, meta.tamano = subida, tipo, tamano
    evento.flyer_url = _url(evento.id, subida, tipo)
    _borrar_archivo_en_disco(anterior)
    db.commit()


def recibir_parte(
    db: Session,
    evento: EventoModel,
    *,
    subida: str,
    orden: int,
    total: int,
    tipo: str,
    tamano_total: int,
    datos: bytes,
) -> bool:
    """Guarda un trozo del archivo. Devuelve True cuando ya llegaron todos y el flyer quedó publicado."""
    if tipo not in FLYER_TYPES:
        raise FlyerError(415, "Usa una imagen JPG, PNG, WEBP o GIF, o un video MP4/WEBM.")
    if not _SUBIDA.match(subida):
        raise FlyerError(400, "Identificador de subida inválido.")
    if not 1 <= total <= MAX_PARTES or not 0 <= orden < total:
        raise FlyerError(400, "Número de partes inválido.")
    limite = limite_para(tipo)
    if tamano_total <= 0 or tamano_total > limite:
        raise FlyerError(
            413, f"El archivo no puede superar {limite // (1024 * 1024)} MB." + (" Las imágenes se comprimen solas; prueba con otra." if limite == MAX_IMAGEN_BYTES else "")
        )
    if len(datos) == 0 or len(datos) > MAX_PARTE_BYTES:
        raise FlyerError(413, "El trozo del archivo es demasiado grande.")
    if orden == 0 and not cabecera_valida(tipo, datos[:16]):
        raise FlyerError(415, "El archivo no parece ser una imagen o video válido.")

    db.execute(
        delete(EventoFlyerParteModel).where(
            EventoFlyerParteModel.evento_id == evento.id,
            EventoFlyerParteModel.subida == subida,
            EventoFlyerParteModel.orden == orden,
        )
    )
    db.add(EventoFlyerParteModel(evento_id=evento.id, subida=subida, orden=orden, datos=datos))
    db.flush()
    vigente = db.get(EventoFlyerModel, evento.id)
    # subidas abandonadas a medias: se limpian (la vigente y la actual se conservan)
    conservar = {subida} | ({vigente.subida} if vigente else set())
    db.execute(
        delete(EventoFlyerParteModel).where(
            EventoFlyerParteModel.evento_id == evento.id, EventoFlyerParteModel.subida.notin_(conservar)
        )
    )
    recibidas, suma = db.execute(
        select(func.count(), func.coalesce(func.sum(func.length(EventoFlyerParteModel.datos)), 0)).where(
            EventoFlyerParteModel.evento_id == evento.id, EventoFlyerParteModel.subida == subida
        )
    ).one()
    if recibidas < total:
        db.commit()
        return False
    if suma != tamano_total:
        db.execute(
            delete(EventoFlyerParteModel).where(
                EventoFlyerParteModel.evento_id == evento.id, EventoFlyerParteModel.subida == subida
            )
        )
        db.commit()
        raise FlyerError(400, "El archivo llegó incompleto. Inténtalo de nuevo.")
    _finalizar(db, evento, subida, tipo, int(suma))
    return True


def guardar_completo(db: Session, evento: EventoModel, tipo: str, contenido: bytes) -> None:
    """Para archivos que caben en una sola solicitud."""
    recibir_parte(
        db, evento, subida=uuid4().hex, orden=0, total=1, tipo=tipo, tamano_total=len(contenido), datos=contenido
    )


def leer_rango(db: Session, evento_id: int, inicio: int | None, fin: int | None):
    """Devuelve (bytes, inicio, fin, total, tipo) o None si el evento no tiene flyer en la base de datos."""
    meta = db.get(EventoFlyerModel, evento_id)
    if meta is None:
        return None
    tamanos = db.execute(
        select(EventoFlyerParteModel.orden, func.length(EventoFlyerParteModel.datos))
        .where(EventoFlyerParteModel.evento_id == evento_id, EventoFlyerParteModel.subida == meta.subida)
        .order_by(EventoFlyerParteModel.orden)
    ).all()
    total = sum(t for _, t in tamanos)
    if total == 0:
        return None
    ini = 0 if inicio is None else inicio
    if ini >= total:
        return b"", ini, ini, total, meta.tipo
    fin_real = total - 1 if fin is None else min(fin, total - 1)
    fin_real = min(fin_real, ini + MAX_RESPUESTA_BYTES - 1)
    contenido = bytearray()
    offset = 0
    for orden, tam in tamanos:
        a, b = offset, offset + tam - 1
        offset += tam
        if b < ini or a > fin_real:
            continue
        datos = db.execute(
            select(EventoFlyerParteModel.datos).where(
                EventoFlyerParteModel.evento_id == evento_id,
                EventoFlyerParteModel.subida == meta.subida,
                EventoFlyerParteModel.orden == orden,
            )
        ).scalar_one()
        contenido += datos[max(ini - a, 0): fin_real - a + 1]
    return bytes(contenido), ini, fin_real, total, meta.tipo
