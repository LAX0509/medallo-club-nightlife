from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base


class AccesoQRModel(Base):
    __tablename__ = "accesos_qr"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('qr', 'cortesia_manual')", name="ck_accesos_qr_tipo"
        ),
        CheckConstraint(
            "resultado IN ('valido', 'duplicado', 'rechazado')",
            name="ck_accesos_qr_resultado",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invitado_id: Mapped[int | None] = mapped_column(
        ForeignKey("invitados.id", ondelete="SET NULL"), nullable=True, index=True
    )
    evento_id: Mapped[int] = mapped_column(
        ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    justificacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    invitado = relationship("InvitadoModel", back_populates="accesos")
    evento = relationship("EventoModel", back_populates="accesos")
