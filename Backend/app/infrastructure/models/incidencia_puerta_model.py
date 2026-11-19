from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class IncidenciaPuertaModel(Base):
    __tablename__ = "incidencias_puerta"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('qr_duplicado', 'qr_rechazado', 'nombre_diferente', 'otra')",
            name="ck_incidencias_puerta_tipo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    evento_id: Mapped[int] = mapped_column(
        ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tipo: Mapped[str] = mapped_column(String(24), nullable=False)
    persona: Mapped[str | None] = mapped_column(String(100), nullable=True)
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
