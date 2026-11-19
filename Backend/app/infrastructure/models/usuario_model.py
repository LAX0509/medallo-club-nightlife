from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base


class UsuarioModel(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(
            "rol IN ('Administrador', 'Promotor', 'Puerta')", name="ck_usuarios_rol"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(String(20), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    eventos_administrados = relationship(
        "EventoModel", back_populates="administrador", cascade="all, delete-orphan"
    )
    invitados_gestionados = relationship(
        "InvitadoModel", back_populates="promotor", cascade="all, delete-orphan"
    )
    comisiones = relationship(
        "ComisionModel", back_populates="promotor", cascade="all, delete-orphan"
    )
