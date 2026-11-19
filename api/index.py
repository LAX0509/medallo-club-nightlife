"""Punto de entrada serverless de Vercel: expone la aplicación FastAPI del Backend.

Vercel detecta la variable ``app`` (ASGI). Todas las rutas de la API llegan aquí mediante los ``rewrites``
de ``vercel.json``; FastAPI recibe la ruta original (``/api/v1/...``, ``/health``, ``/webhooks/...``).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Backend"))

from app.main import app  # noqa: E402,F401
