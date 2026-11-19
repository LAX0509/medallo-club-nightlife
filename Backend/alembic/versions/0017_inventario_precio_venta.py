"""Precio de venta en la discoteca para cada producto del inventario."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017_inventario_precio_venta"
down_revision: Union[str, None] = "0016_evento_flyers_en_bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("inventario_items", sa.Column("precio_venta", sa.Numeric(12, 2), nullable=True))
    op.create_check_constraint(
        "ck_inventario_items_precio_venta_no_negativo",
        "inventario_items",
        "precio_venta IS NULL OR precio_venta >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_inventario_items_precio_venta_no_negativo", "inventario_items", type_="check")
    op.drop_column("inventario_items", "precio_venta")
