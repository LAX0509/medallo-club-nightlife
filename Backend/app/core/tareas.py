"""Ejecución de tareas posteriores a la respuesta (avisos de WhatsApp) segura para entornos serverless.

En un servidor normal (``uvicorn``) las tareas de ``BackgroundTasks`` corren después de responder. En
plataformas serverless como Vercel o AWS Lambda el proceso se congela en cuanto se envía la respuesta, así
que esas tareas pueden no ejecutarse nunca (los avisos «no llegan»). Allí se ejecutan ANTES de responder,
con un plazo corto, y nunca rompen la petición si fallan.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)


def es_serverless() -> bool:
    """True en Vercel/AWS Lambda o si se fuerza con ``NOTIFICACIONES_EN_LINEA=true``."""
    forzado = os.environ.get("NOTIFICACIONES_EN_LINEA", "").strip().lower()
    if forzado in {"1", "true", "si", "sí", "yes"}:
        return True
    if forzado in {"0", "false", "no"}:
        return False
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def lanzar(background_tasks: BackgroundTasks, funcion: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Programa ``funcion`` tras la respuesta, o la ejecuta ya mismo si el entorno es serverless."""
    if not es_serverless():
        background_tasks.add_task(funcion, *args, **kwargs)
        return
    try:
        funcion(*args, **kwargs)
    except Exception:  # un aviso fallido jamás debe tumbar la reserva ya guardada
        logger.exception("Falló la tarea %s ejecutada en línea.", getattr(funcion, "__name__", "?"))
