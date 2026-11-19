from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class InventarioMovimientoModel(Base):
    """Bitácora de existencias: cada entrada, salida, consumo o ajuste queda trazado."""

    __tablename__ = "inventario_movimientos"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('entrada', 'salida', 'consumo', 'ajuste')",
            name="ck_inventario_movimientos_tipo",
        ),
        CheckConstraint("cantidad >= 0", name="ck_inventario_movimientos_cantidad"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventario_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cantidad_anterior: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cantidad_nueva: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evento_id: Mapped[int | None] = mapped_column(
        ForeignKey("eventos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
