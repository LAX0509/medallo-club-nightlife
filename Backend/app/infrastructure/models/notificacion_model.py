from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class NotificacionModel(Base):
    """Notificación interna (campana del panel). Complementa los avisos por WhatsApp."""

    __tablename__ = "notificaciones"
    __table_args__ = (
        CheckConstraint("nivel IN ('info', 'alerta', 'critica')", name="ck_notificaciones_nivel"),
        Index("ix_notificaciones_leida_creada", "leida", "creada_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(120), nullable=False)
    mensaje: Mapped[str] = mapped_column(String(400), nullable=False)
    nivel: Mapped[str] = mapped_column(String(10), nullable=False, default="info")
    enlace: Mapped[str | None] = mapped_column(String(200), nullable=True)
    referencia: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    destinatario_rol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    destinatario_usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=True, index=True
    )
    leida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    leida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
