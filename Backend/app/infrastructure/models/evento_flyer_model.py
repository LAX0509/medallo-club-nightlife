from sqlalchemy import ForeignKey, Index, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class EventoFlyerModel(Base):
    """Metadatos del flyer (imagen o video) vigente de un evento; el contenido está en las partes."""

    __tablename__ = "evento_flyers"

    evento_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("eventos.id", ondelete="CASCADE"), primary_key=True
    )
    subida: Mapped[str] = mapped_column(String(36), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    tamano: Mapped[int] = mapped_column(Integer, nullable=False)


class EventoFlyerParteModel(Base):
    """Trozo del archivo de un flyer.

    El archivo se guarda en la base de datos porque en el hosting sin servidor el disco es de solo lectura,
    y en trozos porque cada solicitud HTTP del hosting admite como máximo ~4,5 MB.
    """

    __tablename__ = "evento_flyer_partes"
    __table_args__ = (
        UniqueConstraint("evento_id", "subida", "orden", name="uq_evento_flyer_partes_orden"),
        Index("ix_evento_flyer_partes_evento_subida", "evento_id", "subida"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evento_id: Mapped[int] = mapped_column(Integer, ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False)
    subida: Mapped[str] = mapped_column(String(36), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    datos: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
