from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class BotConfiguracionModel(Base):
    """Parámetros editables del asistente (saludo, horarios, políticas, IA activa...)."""

    __tablename__ = "bot_configuracion"

    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
