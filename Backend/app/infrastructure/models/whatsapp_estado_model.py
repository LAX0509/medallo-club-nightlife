from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class WhatsAppEstadoModel(Base):
    """Estado de entrega que Meta reporta por webhook para cada mensaje enviado (sent/delivered/read/failed).

    Solo guarda metadatos: del destinatario se conservan únicamente los últimos 4 dígitos.
    """

    __tablename__ = "whatsapp_estados"
    __table_args__ = (
        Index("ix_whatsapp_estados_message_id", "message_id"),
        Index("ix_whatsapp_estados_creado_en", "creado_en"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    destinatario_fin: Mapped[str | None] = mapped_column(String(8), nullable=True)
    codigo_error: Mapped[str | None] = mapped_column(String(20), nullable=True)
    titulo_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    detalle_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
