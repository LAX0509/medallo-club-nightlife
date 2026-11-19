from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base


class ComisionModel(Base):
    __tablename__ = "comisiones"
    __table_args__ = (
        CheckConstraint(
            "porcentaje >= 0 AND porcentaje <= 100", name="ck_comisiones_porcentaje"
        ),
        CheckConstraint("monto >= 0", name="ck_comisiones_monto_no_negativo"),
        CheckConstraint(
            "estado IN ('pendiente', 'liquidada')", name="ck_comisiones_estado"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    promotor_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    evento_id: Mapped[int] = mapped_column(
        ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    porcentaje: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    monto: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    fecha_liquidacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    promotor = relationship("UsuarioModel", back_populates="comisiones")
    evento = relationship("EventoModel", back_populates="comisiones")
