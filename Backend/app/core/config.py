from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración central de la aplicación, cargada desde variables de entorno (.env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Aplicación
    app_name: str = "Nightlife Data Scientist API"
    app_version: str = "1.0.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    # Base de datos
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/nightlife_db"

    # URL directa (sin pooler). La integración de Neon la entrega como DATABASE_URL_UNPOOLED; el bloqueo de
    # ingresos usa ``pg_advisory_lock`` de sesión, que NO funciona detrás de PgBouncer (pooler de Neon).
    database_url_unpooled: str = ""

    @model_validator(mode="after")
    def _preferir_url_directa(self) -> "Settings":
        if self.database_url_unpooled.strip():
            self.database_url = self._normalizar_url_bd(self.database_url_unpooled)
        return self

    @field_validator("database_url")
    @classmethod
    def _normalizar_url_bd(cls, valor: str) -> str:
        """Neon/Vercel/Render entregan ``postgres://`` o ``postgresql://``: SQLAlchemy necesita el driver."""
        valor = valor.strip()
        for prefijo in ("postgres://", "postgresql://"):
            if valor.startswith(prefijo):
                return "postgresql+psycopg2://" + valor[len(prefijo):]
        return valor

    # Seguridad / JWT
    jwt_secret_key: str = "CHANGE_ME_INSECURE_DEFAULT_SECRET_KEY"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # WhatsApp Cloud API: dejar vacío hasta completar la configuración de Meta.
    whatsapp_graph_api_version: str = "v26.0"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_notify_to: str = ""
    whatsapp_template_name: str = "medallo_nueva_reserva"
    whatsapp_template_language: str = "es"
    whatsapp_confirmation_template_name: str = ""
    whatsapp_confirmation_template_language: str = "es"
    whatsapp_reservation_url_prefix: str = ""
    whatsapp_reservation_page_url: str = ""
    whatsapp_inventory_notify_to: str = ""
    whatsapp_inventory_template_name: str = ""
    whatsapp_inventory_template_language: str = "es"
    whatsapp_webhook_verify_token: str = ""
    whatsapp_app_secret: str = ""

    # Asistente de IA (Google Gemini). Sin API key el bot funciona con su motor local.
    # La clave gratuita se obtiene en https://aistudio.google.com/apikey (sin tarjeta).
    gemini_api_key: str = ""
    # Claves adicionales (separadas por coma), de OTROS proyectos de Google: cada proyecto tiene su propia cuota.
    gemini_api_keys_extra: str = ""
    gemini_model: str = "gemini-3.6-flash"
    # Modelos de respaldo (separados por coma) si el principal no existe o agota su cuota gratuita.
    gemini_model_respaldo: str = "gemini-3.5-flash,gemini-2.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    gemini_timeout_seconds: float = 20.0

    # Proveedor de respaldo gratuito (Groq, API compatible con OpenAI): responde si toda la cadena de
    # Gemini falla o se agota. Clave gratis en https://console.groq.com/keys
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_model_respaldo: str = "qwen/qwen3.8-27b,openai/gpt-oss-20b"
    groq_timeout_seconds: float = 10.0

    # URL pública del frontend (enlaces de pases, reservas y calendario).
    public_frontend_url: str = "http://localhost:5173"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Reglas de negocio
    valor_base_por_invitado_cop: float = 20000.0
    umbral_sobreaforo_medio: float = 0.85
    umbral_sobreaforo_alto: float = 1.0
    umbral_zscore_comision_atipica: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
