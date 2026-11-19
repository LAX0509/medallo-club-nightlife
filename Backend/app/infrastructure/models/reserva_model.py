from datetime import datetime

from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class ReservaModel(Base):
    __tablename__ = "reservas"
    __table_args__ = (
        CheckConstraint("tipo IN ('mesa', 'palco')", name="ck_reservas_tipo"),
        CheckConstraint(
            "estado IN ('pendiente', 'confirmada', 'cancelada')",
            name="ck_reservas_estado",
        ),
        CheckConstraint("asistentes > 0", name="ck_reservas_asistentes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    evento_id: Mapped[int] = mapped_column(
        ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    promotor_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nombre_cliente: Mapped[str] = mapped_column(String(100), nullable=False)
    telefono: Mapped[str] = mapped_column(String(24), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    asistentes: Mapped[int] = mapped_column(Integer, nullable=False)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_cancelacion_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    whatsapp_confirmacion_estado: Mapped[str] = mapped_column(String(20), nullable=False, default="sin_configurar", server_default="sin_configurar")
    whatsapp_confirmacion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_confirmacion_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    codigo_garantia: Mapped[str | None] = mapped_column(String(24), nullable=True, unique=True)
    garantizada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hora_limite: Mapped[str | None] = mapped_column(String(5), nullable=True)
    ubicacion_asignada: Mapped[str | None] = mapped_column(String(60), nullable=True)
    consumo_minimo: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    fecha_solicitud: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
