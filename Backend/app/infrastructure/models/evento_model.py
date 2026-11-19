from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base


class EventoModel(Base):
    __tablename__ = "eventos"
    __table_args__ = (
        CheckConstraint("aforo_maximo > 0", name="ck_eventos_aforo_positivo"),
        CheckConstraint(
            "estado IN ('planeado', 'en curso', 'cerrado')", name="ck_eventos_estado"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    administrador_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    aforo_maximo: Mapped[int] = mapped_column(Integer, nullable=False)
    tematica: Mapped[str | None] = mapped_column(String(240), nullable=True)
    flyer_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="planeado")

    administrador = relationship("UsuarioModel", back_populates="eventos_administrados")
    invitados = relationship(
        "InvitadoModel", back_populates="evento", cascade="all, delete-orphan"
    )
    comisiones = relationship(
        "ComisionModel", back_populates="evento", cascade="all, delete-orphan"
    )
    accesos = relationship(
        "AccesoQRModel", back_populates="evento", cascade="all, delete-orphan"
    )
    alertas = relationship(
        "AlertaRiesgoModel", back_populates="evento", cascade="all, delete-orphan"
    )
