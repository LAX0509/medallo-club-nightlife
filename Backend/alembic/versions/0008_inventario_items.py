"""Add basic inventory items and stock levels."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_inventario_items"
down_revision: Union[str, None] = "0007_incidencias_puerta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventario_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("categoria", sa.String(length=60), nullable=True),
        sa.Column("cantidad", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("unidad", sa.String(length=20), nullable=False, server_default="unidades"),
        sa.Column("stock_minimo", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("cantidad >= 0", name="ck_inventario_items_cantidad_no_negativa"),
        sa.CheckConstraint("stock_minimo >= 0", name="ck_inventario_items_minimo_no_negativo"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventario_items_nombre", "inventario_items", ["nombre"])


def downgrade() -> None:
    op.drop_index("ix_inventario_items_nombre", table_name="inventario_items")
    op.drop_table("inventario_items")
