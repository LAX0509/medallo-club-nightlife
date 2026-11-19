from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class ChatSesionModel(Base):
    """Conversación del asistente. En WhatsApp solo se guarda metadata, no el texto."""

    __tablename__ = "chat_sesiones"
    __table_args__ = (
        CheckConstraint("canal IN ('web', 'whatsapp')", name="ck_chat_sesiones_canal"),
        Index("ix_chat_sesiones_actualizada", "actualizada_en"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canal: Mapped[str] = mapped_column(String(10), nullable=False)
    contacto_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    estado_dialogo: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    mensajes_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    negativos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sentimiento_promedio: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=0)
    escalada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    escalada_resuelta: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    reserva_id: Mapped[int | None] = mapped_column(
        ForeignKey("reservas.id", ondelete="SET NULL"), nullable=True
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ChatMensajeModel(Base):
    __tablename__ = "chat_mensajes"
    __table_args__ = (
        CheckConstraint("autor IN ('usuario', 'bot')", name="ck_chat_mensajes_autor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sesion_id: Mapped[str] = mapped_column(
        ForeignKey("chat_sesiones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    autor: Mapped[str] = mapped_column(String(10), nullable=False)
    texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentimiento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    puntaje: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    emocion: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aspectos: Mapped[str | None] = mapped_column(String(200), nullable=True)
    intencion: Mapped[str | None] = mapped_column(String(30), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
