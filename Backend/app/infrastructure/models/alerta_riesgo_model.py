from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base


class AlertaRiesgoModel(Base):
    __tablename__ = "alertas_riesgo"
    __table_args__ = (
        CheckConstraint(
            "tipo_alerta IN ('sobreaforo', 'comision_atipica', 'cortesia_duplicada')",
            name="ck_alertas_tipo",
        ),
        CheckConstraint("nivel IN ('bajo', 'medio', 'alto')", name="ck_alertas_nivel"),
        CheckConstraint(
            "estado IN ('activa', 'resuelta')", name="ck_alertas_estado"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    evento_id: Mapped[int] = mapped_column(
        ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo_alerta: Mapped[str] = mapped_column(String(50), nullable=False)
    nivel: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="activa")
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    evento = relationship("EventoModel", back_populates="alertas")
