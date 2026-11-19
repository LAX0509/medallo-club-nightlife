from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base


class InvitadoModel(Base):
    __tablename__ = "invitados"
    __table_args__ = (
        CheckConstraint("estado IN ('pendiente', 'usado')", name="ck_invitados_estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    evento_id: Mapped[int] = mapped_column(
        ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    promotor_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reserva_id: Mapped[int | None] = mapped_column(
        ForeignKey("reservas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    qr_code: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    evento = relationship("EventoModel", back_populates="invitados")
    promotor = relationship("UsuarioModel", back_populates="invitados_gestionados")
    accesos = relationship(
        "AccesoQRModel", back_populates="invitado", cascade="all, delete-orphan"
    )
