from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class InventarioItemModel(Base):
    __tablename__ = "inventario_items"
    __table_args__ = (
        CheckConstraint("cantidad >= 0", name="ck_inventario_items_cantidad_no_negativa"),
        CheckConstraint("stock_minimo >= 0", name="ck_inventario_items_minimo_no_negativo"),
        CheckConstraint(
            "precio_venta IS NULL OR precio_venta >= 0", name="ck_inventario_items_precio_venta_no_negativo"
        ),
        Index("ix_inventario_items_nombre", "nombre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    categoria: Mapped[str | None] = mapped_column(String(60), nullable=True)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    unidad: Mapped[str] = mapped_column(String(20), nullable=False, default="unidades")
    stock_minimo: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    costo_unitario: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    precio_venta: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    proveedor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
