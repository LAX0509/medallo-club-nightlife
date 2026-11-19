from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.error_handlers import register_exception_handlers
from app.api.v1.router import api_router
from app.api.v1.whatsapp_router import router as whatsapp_webhook_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="API para la gestión de bares, discotecas, eventos, promotores y reservas",
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # En desarrollo permite abrir el frontend desde otros dispositivos de la
    # misma red privada (por ejemplo, http://192.168.1.20:5173 desde el celular).
    # En producción se deben declarar los dominios exactos en CORS_ORIGINS.
    allow_origin_regex=(
        r"^https?://(?:localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|"
        r"192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?::\d+)?$"
        if settings.environment.lower() == "development"
        else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(whatsapp_webhook_router)

uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
try:
    uploads_dir.mkdir(parents=True, exist_ok=True)
except OSError:  # disco de solo lectura (serverless): se sirve lo que ya venga en el repositorio
    pass
if uploads_dir.is_dir():
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Nightlife Data Scientist API funcionando correctamente"
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok"
    }
