from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class WhatsAppInboundMessageModel(Base):
    """Sentiment metadata only; raw message text and phone are not retained."""

    __tablename__ = "whatsapp_inbound_messages"
    __table_args__ = (Index("ix_whatsapp_inbound_received_at", "received_at"),)

    message_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    sender_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    response_status: Mapped[str] = mapped_column(String(20), nullable=False, default="procesando")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
