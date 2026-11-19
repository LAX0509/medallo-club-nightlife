"""Attribute public reservations to a promoter referral.

Revision ID: 0006_atribucion_reserva_promotor
Revises: 0005_metas_promotores
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_atribucion_reserva_promotor"
down_revision: Union[str, None] = "0005_metas_promotores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reservas", sa.Column("promotor_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_reservas_promotor_id_usuarios",
        "reservas",
        "usuarios",
        ["promotor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_reservas_promotor_id", "reservas", ["promotor_id"])


def downgrade() -> None:
    op.drop_index("ix_reservas_promotor_id", table_name="reservas")
    op.drop_constraint("fk_reservas_promotor_id_usuarios", "reservas", type_="foreignkey")
    op.drop_column("reservas", "promotor_id")
