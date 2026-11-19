"""Formatos de QR de Medallo Club: lectura (detección) y escritura (payloads).

El identificador del pase siempre es el código ``NLD-<evento>-<token>``. Para facilitar
la operación en puerta, el QR puede *contener* ese código de varias formas y el sistema
reconoce todas al escanear:

* ``codigo``    -> el código tal cual.
* ``url``       -> enlace público del pase (``https://.../pase/<codigo>``).
* ``esquema``   -> enlace profundo de la app (``medallo://pase/<codigo>``).
* ``json``      -> objeto JSON (``{"app": "medallo-club", "v": 1, "qr": "<codigo>"}``).
* ``base64``    -> cualquiera de los anteriores codificado en base64 / base64url.
* ``texto``     -> texto compartido que incluye el código (p. ej. un mensaje de WhatsApp).
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, unquote, urlsplit

_TOKEN = r"NLD-\d+-[A-Za-z0-9_-]{16,64}"
_PATTERN = re.compile(rf"^{_TOKEN}$")
_EMBEBIDO = re.compile(rf"(?<![A-Za-z0-9_-])({_TOKEN})(?![A-Za-z0-9_-])")
_BASE64 = re.compile(r"^[A-Za-z0-9+/_-]{24,}={0,2}$")
_INVISIBLES = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)
_QUERY_KEYS = ("qr", "qr_code", "codigo", "code", "data")
MAX_LONGITUD = 2048

FORMATOS_ESCRITURA = ("codigo", "url", "esquema", "json", "base64")

DESCRIPCION_FORMATOS = {
    "codigo": "Código del pase (el más simple y rápido de leer)",
    "url": "Enlace público del pase; abre la página del pase en cualquier celular",
    "esquema": "Enlace profundo medallo://pase/<código> para la app del equipo",
    "json": "Objeto JSON con versión y código, apto para integraciones",
    "base64": "JSON codificado en base64url, útil cuando el lector altera símbolos",
}


@dataclass(frozen=True)
class QrLectura:
    codigo: str
    formato: str


def _limpiar(valor: str) -> str:
    return unquote(valor.translate(_INVISIBLES).strip())


def _claves_json(objeto: dict) -> list[str]:
    encontrados = [str(objeto[k]) for k in _QUERY_KEYS if objeto.get(k) and not isinstance(objeto[k], dict)]
    anidado = objeto.get("data")
    if isinstance(anidado, dict):
        encontrados.extend(_claves_json(anidado))
    return encontrados


def _desde_url(texto: str) -> str | None:
    partes = urlsplit(texto)
    if not (partes.scheme in ("http", "https", "medallo") or partes.netloc):
        return None
    consulta = parse_qs(partes.query)
    for clave in _QUERY_KEYS:
        for item in consulta.get(clave, []):
            if _PATTERN.fullmatch(item.strip()):
                return item.strip()
    segmentos = [partes.netloc, *partes.path.split("/")] if partes.scheme == "medallo" else partes.path.split("/")
    for segmento in reversed(segmentos):
        if _PATTERN.fullmatch(segmento):
            return segmento
    return None


def _detectar(texto: str, profundidad: int) -> QrLectura | None:
    if _PATTERN.fullmatch(texto):
        return QrLectura(texto, "codigo")

    if texto.startswith("{"):
        try:
            objeto = json.loads(texto)
        except json.JSONDecodeError:
            objeto = None
        if isinstance(objeto, dict):
            for candidato in _claves_json(objeto):
                if _PATTERN.fullmatch(candidato.strip()):
                    return QrLectura(candidato.strip(), "json")

    codigo_url = _desde_url(texto)
    if codigo_url:
        esquema = urlsplit(texto).scheme
        return QrLectura(codigo_url, "esquema" if esquema == "medallo" else "url")

    if profundidad == 0 and _BASE64.fullmatch(texto):
        relleno = "=" * (-len(texto) % 4)
        for decodificador in (base64.urlsafe_b64decode, base64.b64decode):
            try:
                decodificado = decodificador(texto + relleno).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                continue
            interno = _detectar(_limpiar(decodificado), profundidad + 1)
            if interno:
                return QrLectura(interno.codigo, "base64")

    # Prefijo en minúsculas (p. ej. teclado móvil que capitaliza distinto).
    if texto[:4].lower() == "nld-" and texto[:4] != "NLD-":
        corregido = "NLD-" + texto[4:]
        if _PATTERN.fullmatch(corregido):
            return QrLectura(corregido, "codigo")

    embebido = _EMBEBIDO.search(texto)
    if embebido:
        return QrLectura(embebido.group(1), "texto")
    return None


def leer_qr(valor: str | None) -> QrLectura:
    """Interpreta el contenido de un QR y devuelve el código del pase y el formato detectado."""
    if not isinstance(valor, str):
        raise ValueError("El contenido del QR debe ser texto.")
    if len(valor) > MAX_LONGITUD:
        raise ValueError("El contenido del QR es demasiado largo.")
    resultado = _detectar(_limpiar(valor), 0)
    if resultado is None:
        raise ValueError(
            "Formato QR no reconocido. Usa el código NLD del pase o su enlace/JSON de acceso."
        )
    return resultado


def normalizar_codigo_qr(valor: str | None) -> str:
    return leer_qr(valor).codigo


def construir_payload_qr(
    codigo: str,
    formato: str = "codigo",
    *,
    base_url: str = "",
    evento_id: int | None = None,
) -> str:
    """Genera el texto que se incrusta en el QR para el formato elegido."""
    if not _PATTERN.fullmatch(codigo):
        raise ValueError("Código de pase no válido.")
    base = base_url.rstrip("/")
    if formato == "codigo":
        return codigo
    if formato == "url":
        return f"{base}/pase/{quote(codigo)}" if base else f"/pase/{quote(codigo)}"
    if formato == "esquema":
        return f"medallo://pase/{codigo}"
    cuerpo = {"app": "medallo-club", "v": 1, "qr": codigo}
    if evento_id is not None:
        cuerpo["evento"] = evento_id
    texto_json = json.dumps(cuerpo, separators=(",", ":"))
    if formato == "json":
        return texto_json
    if formato == "base64":
        return base64.urlsafe_b64encode(texto_json.encode("utf-8")).decode("ascii").rstrip("=")
    raise ValueError(f"Formato de QR no soportado: {formato}")
