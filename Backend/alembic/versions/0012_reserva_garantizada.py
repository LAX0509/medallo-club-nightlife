"""Reserva garantizada: código de garantía, condiciones y pases vinculados."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012_reserva_garantizada"
down_revision: Union[str, None] = "0011_notif_inventario_mov"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reservas", sa.Column("codigo_garantia", sa.String(length=24), nullable=True))
    op.add_column("reservas", sa.Column("garantizada_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reservas", sa.Column("hora_limite", sa.String(length=5), nullable=True))
    op.add_column("reservas", sa.Column("ubicacion_asignada", sa.String(length=60), nullable=True))
    op.add_column("reservas", sa.Column("consumo_minimo", sa.Numeric(12, 2), nullable=True))
    op.create_unique_constraint("uq_reservas_codigo_garantia", "reservas", ["codigo_garantia"])

    op.add_column("invitados", sa.Column("reserva_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_invitados_reserva_id", "invitados", "reservas", ["reserva_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_invitados_reserva_id", "invitados", ["reserva_id"])


def downgrade() -> None:
    op.drop_index("ix_invitados_reserva_id", table_name="invitados")
    op.drop_constraint("fk_invitados_reserva_id", "invitados", type_="foreignkey")
    op.drop_column("invitados", "reserva_id")
    op.drop_constraint("uq_reservas_codigo_garantia", "reservas", type_="unique")
    for columna in ("consumo_minimo", "ubicacion_asignada", "hora_limite", "garantizada_en", "codigo_garantia"):
        op.drop_column("reservas", columna)
