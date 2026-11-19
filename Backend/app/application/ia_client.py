"""Cliente de IA (Google Gemini) del asistente.

Reglas de diseño:
* Usa el SDK oficial ``google-genai`` y *salida estructurada* (JSON que cumple un esquema).
* Pensado para la capa gratuita de Google AI Studio. La cuota gratuita es POR MODELO y POR PROYECTO de
  Google, así que la consulta recorre una cadena de modelos y, para cada modelo, las claves configuradas
  (``GEMINI_API_KEY`` + ``GEMINI_API_KEYS_EXTRA``, de proyectos distintos): si una se agota o falla,
  responde la siguiente.
* Si toda la cadena de Gemini falla, se prueba un proveedor de respaldo gratuito (Groq, API compatible con
  OpenAI) cuando ``GROQ_API_KEY`` está configurada.
* Es opcional: sin clave (o con el interruptor apagado) el asistente funciona con su motor local.
  Cualquier fallo del proveedor se traduce a ``IANoDisponible`` y el llamador usa el plan B; nunca se
  rompe la conversación.
* No registra el contenido de los mensajes de los clientes ni las claves en los logs.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import date
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class IANoDisponible(Exception):
    """El proveedor de IA no está configurado, está agotado o falló."""


class LimiteDiario:
    """Tope diario de llamadas para acotar el consumo (en memoria; se reinicia cada día)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._dia = date.today()
        self._usadas = 0

    def consumir(self, maximo: int) -> bool:
        with self._lock:
            hoy = date.today()
            if hoy != self._dia:
                self._dia, self._usadas = hoy, 0
            if self._usadas >= maximo:
                return False
            self._usadas += 1
            return True

    @property
    def usadas(self) -> int:
        with self._lock:
            return self._usadas if date.today() == self._dia else 0


_limite = LimiteDiario()


def llamadas_ia_hoy() -> int:
    return _limite.usadas


# Códigos HTTP tras los cuales tiene sentido probar otro modelo u otra clave (no existe / cuota agotada /
# saturado / argumento no soportado por ese modelo). 401/403 son de la CLAVE: se descarta esa clave.
_CODIGOS_REINTENTABLES = {400, 404, 429, 500, 502, 503, 504}
_CODIGOS_DE_CLAVE = {401, 403}

# Segundos que se «enfría» un modelo (con una clave) tras fallar: la cuota por minuto se recupera en ~60 s.
_PAUSA_POR_CODIGO = {429: 60.0, 404: 3600.0, 400: 300.0}
_enfriados: dict[str, float] = {}  # «modelo#n» o «clave#n» -> instante (monotonic) hasta el que se omite
_PLAZO_MINIMO = 10.0  # Gemini rechaza (HTTP 400) plazos de solicitud menores a 10 s


def _pausa_sugerida(exc: Exception) -> float | None:
    """Lee el «Please retry in 15h13m51.2s» que Google incluye en los 429 (tope de 6 h)."""
    m = re.search(r"retry in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", str(exc))
    if not m or not any(m.groups()):
        return None
    horas, minutos, segundos = (float(g) if g else 0.0 for g in m.groups())
    return min(max(horas * 3600 + minutos * 60 + segundos, 30.0), 6 * 3600.0)


class ClienteIA:
    def __init__(self, settings: Settings | None = None, *, habilitada: bool = True, limite_diario: int = 200):
        self._settings = settings or get_settings()
        self._habilitada = habilitada
        self._limite_diario = limite_diario
        self._clientes: dict[int, Any] = {}
        self._modelo_activo: str | None = None
        self._clave_activa: int | None = None

    def _claves(self) -> list[str]:
        principal = getattr(self._settings, "gemini_api_key", "") or ""
        extras = (getattr(self._settings, "gemini_api_keys_extra", "") or "").split(",")
        return list(dict.fromkeys(c.strip() for c in [principal, *extras] if c and c.strip()))

    def _clave_groq(self) -> str:
        return (getattr(self._settings, "groq_api_key", "") or "").strip()

    @property
    def configurada(self) -> bool:
        return bool(self._claves()) or bool(self._clave_groq())

    @property
    def con_groq(self) -> bool:
        return bool(self._clave_groq())

    @property
    def disponible(self) -> bool:
        return self.configurada and self._habilitada

    @property
    def modelo(self) -> str:
        return self._modelo_activo or getattr(self._settings, "gemini_model", "")

    @property
    def claves_configuradas(self) -> int:
        return len(self._claves())

    def _modelos(self) -> list[str]:
        principal = self._settings.gemini_model.strip()
        respaldo = [m.strip() for m in self._settings.gemini_model_respaldo.split(",") if m.strip()]
        return list(dict.fromkeys([principal, *respaldo]))

    def _sdk(self, indice: int = 0):
        if indice not in self._clientes:
            from google import genai  # importación diferida: el resto del sistema no depende del SDK
            from google.genai import types

            self._clientes[indice] = genai.Client(
                api_key=self._claves()[indice],
                http_options=types.HttpOptions(timeout=int(self._settings.gemini_timeout_seconds * 1000)),
            )
        return self._clientes[indice]

    def json(
        self,
        *,
        system: str,
        mensajes: list[dict[str, str]],
        esquema: dict[str, Any],
        max_tokens: int = 1500,
    ) -> dict[str, Any]:
        """Pide una respuesta JSON que cumple ``esquema``. Lanza ``IANoDisponible`` si falla."""
        if not self.disponible:
            raise IANoDisponible("La IA no está configurada o está desactivada.")
        if not _limite.consumir(self._limite_diario):
            raise IANoDisponible("Se alcanzó el límite diario de consultas a la IA.")

        fallo: IANoDisponible | None = None
        if self._claves():
            try:
                return self._json_gemini(system, mensajes, esquema, max_tokens)
            except IANoDisponible as exc:
                fallo = exc
        if self.con_groq:
            try:
                return self._json_groq(system, mensajes, esquema, max_tokens)
            except IANoDisponible as exc:
                fallo = exc
        raise fallo or IANoDisponible("La IA no está configurada o está desactivada.")

    def _json_gemini(
        self, system: str, mensajes: list[dict[str, str]], esquema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        try:
            from google.genai import errors, types
        except ImportError as exc:
            raise IANoDisponible("Falta instalar la librería google-genai.") from exc

        contenidos = [
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part(text=m["content"])],
            )
            for m in mensajes
        ]

        def configuracion(modelo: str, restante: float, con_pensamiento: bool = True) -> Any:
            # Clasificar y extraer datos no necesita «razonar»: sin pensamiento el chat responde en ~1-2 s.
            # Gemini 3 se controla con thinking_level; Gemini 2.5, con thinking_budget.
            pensamiento = None
            if con_pensamiento:
                pensamiento = (
                    types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL)
                    if modelo.startswith("gemini-3")
                    else types.ThinkingConfig(thinking_budget=0)
                )
            return types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=esquema,
                max_output_tokens=max_tokens,
                temperature=0.3,
                thinking_config=pensamiento,
                http_options=types.HttpOptions(timeout=int(restante * 1000)),
            )

        def llamar(modelo: str, indice: int, restante: float) -> Any:
            generar = self._sdk(indice).models.generate_content
            try:
                return generar(model=modelo, contents=contenidos, config=configuracion(modelo, restante))
            except errors.APIError as exc:
                if getattr(exc, "code", None) == 400 and "thinking" in str(exc).lower():
                    # Algunos modelos no admiten ese nivel de razonamiento: se reintenta con el valor por defecto.
                    return generar(model=modelo, contents=contenidos, config=configuracion(modelo, restante, False))
                raise

        ultimo_error = "No se pudo consultar la IA."
        inicio = time.monotonic()
        presupuesto = float(self._settings.gemini_timeout_seconds)  # tope TOTAL de la consulta, con respaldos
        n_claves = self.claves_configuradas
        hubo_intento = False
        # Primero se agota la cadena de modelos con cada clave: la cuota es por modelo y por proyecto.
        for modelo in self._modelos():
            for indice in range(n_claves):
                ahora = time.monotonic()
                if _enfriados.get(f"clave#{indice}", 0.0) > ahora or _enfriados.get(f"{modelo}#{indice}", 0.0) > ahora:
                    ultimo_error = "Los modelos de IA están en pausa temporal (cuota o saturación)."
                    continue
                restante = presupuesto - (time.monotonic() - inicio)
                if hubo_intento and restante < _PLAZO_MINIMO:
                    raise IANoDisponible("La IA tardó demasiado en responder.")  # sin tiempo para otro intento
                hubo_intento = True
                try:
                    respuesta = llamar(modelo, indice, max(restante, _PLAZO_MINIMO))
                except errors.APIError as exc:
                    codigo = getattr(exc, "code", None)
                    logger.warning("Gemini (%s, clave %s) respondió HTTP %s.", modelo, indice + 1, codigo)
                    ultimo_error = f"Error del proveedor de IA (HTTP {codigo})."
                    if codigo in _CODIGOS_DE_CLAVE:
                        _enfriados[f"clave#{indice}"] = time.monotonic() + 3600.0  # clave inválida o revocada
                        continue
                    if codigo in _CODIGOS_REINTENTABLES:
                        # No se vuelve a molestar a ese modelo/clave por un rato: el chat usa el siguiente o el motor local.
                        pausa = _pausa_sugerida(exc) or _PAUSA_POR_CODIGO.get(codigo, 30.0)
                        _enfriados[f"{modelo}#{indice}"] = time.monotonic() + pausa
                        continue
                    raise IANoDisponible(ultimo_error) from exc  # solicitud rechazada por otra causa
                except Exception as exc:  # red, tiempo de espera, SDK
                    logger.warning("No se pudo consultar Gemini (%s): %s.", modelo, type(exc).__name__)
                    _enfriados[f"{modelo}#{indice}"] = time.monotonic() + 30.0
                    raise IANoDisponible("No se pudo consultar la IA.") from exc

                texto = (getattr(respuesta, "text", None) or "").strip()
                if not texto:
                    ultimo_error = "La IA no entregó una respuesta utilizable (bloqueada o vacía)."
                    continue
                try:
                    datos = json.loads(texto)
                except json.JSONDecodeError:
                    ultimo_error = "La IA devolvió un formato no válido."
                    continue
                if not isinstance(datos, dict):
                    ultimo_error = "La IA devolvió un formato no válido."
                    continue
                self._modelo_activo, self._clave_activa = modelo, indice
                return datos
        raise IANoDisponible(ultimo_error)

    def _json_groq(
        self, system: str, mensajes: list[dict[str, str]], esquema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        """Respaldo en Groq (API compatible con OpenAI, modo JSON). Misma interfaz y mismos errores."""
        ajustes = self._settings
        modelos = list(dict.fromkeys(
            m.strip() for m in [ajustes.groq_model, *ajustes.groq_model_respaldo.split(",")] if m and m.strip()
        ))
        instruccion = (
            f"{system}\n\nResponde SOLO con un objeto JSON válido que cumpla este esquema JSON "
            f"(sin texto adicional):\n{json.dumps(esquema, ensure_ascii=False)}"
        )
        historial = [{"role": "system", "content": instruccion}, *mensajes]
        ultimo_error = "No se pudo consultar el proveedor de respaldo."
        for modelo in modelos:
            if _enfriados.get(f"groq:{modelo}", 0.0) > time.monotonic() or _enfriados.get("groq:clave", 0.0) > time.monotonic():
                ultimo_error = "El proveedor de respaldo está en pausa temporal (cuota o saturación)."
                continue
            try:
                r = httpx.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._clave_groq()}"},
                    json={
                        "model": modelo,
                        "messages": historial,
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3,
                        "max_tokens": max_tokens,
                    },
                    timeout=float(ajustes.groq_timeout_seconds),
                )
            except (httpx.HTTPError, AssertionError) as exc:  # red / tiempo de espera
                logger.warning("No se pudo consultar Groq (%s): %s.", modelo, type(exc).__name__)
                _enfriados[f"groq:{modelo}"] = time.monotonic() + 30.0
                raise IANoDisponible("No se pudo consultar el proveedor de respaldo.") from exc
            if r.status_code != 200:
                logger.warning("Groq (%s) respondió HTTP %s.", modelo, r.status_code)
                ultimo_error = f"Error del proveedor de respaldo (HTTP {r.status_code})."
                if r.status_code in _CODIGOS_DE_CLAVE:
                    _enfriados["groq:clave"] = time.monotonic() + 3600.0
                    break
                if r.status_code in _CODIGOS_REINTENTABLES:
                    try:
                        pausa = float(r.headers.get("retry-after", ""))
                    except ValueError:
                        pausa = _PAUSA_POR_CODIGO.get(r.status_code, 30.0)
                    _enfriados[f"groq:{modelo}"] = time.monotonic() + min(max(pausa, 10.0), 6 * 3600.0)
                    continue
                raise IANoDisponible(ultimo_error)
            try:
                texto = (r.json()["choices"][0]["message"]["content"] or "").strip()
                datos = json.loads(texto)
            except (KeyError, IndexError, TypeError, ValueError):
                ultimo_error = "El proveedor de respaldo devolvió un formato no válido."
                continue
            if not isinstance(datos, dict):
                ultimo_error = "El proveedor de respaldo devolvió un formato no válido."
                continue
            self._modelo_activo, self._clave_activa = modelo, None
            return datos
        raise IANoDisponible(ultimo_error)
