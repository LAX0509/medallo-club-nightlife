"""Add per-event targets for promoter accounts.

Revision ID: 0005_metas_promotores
Revises: 0004_token_cancelacion_reserva
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_metas_promotores"
down_revision: Union[str, None] = "0004_token_cancelacion_reserva"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "promotores_metas_evento",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("promotor_id", sa.Integer(), nullable=False),
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("objetivo", sa.Integer(), nullable=False),
        sa.CheckConstraint("objetivo > 0", name="ck_promotor_meta_objetivo_positivo"),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["promotor_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("promotor_id", "evento_id", name="uq_promotor_meta_evento"),
    )
    op.create_index(
        "ix_promotores_metas_evento_promotor_id",
        "promotores_metas_evento",
        ["promotor_id"],
    )
    op.create_index(
        "ix_promotores_metas_evento_evento_id",
        "promotores_metas_evento",
        ["evento_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_promotores_metas_evento_evento_id", table_name="promotores_metas_evento")
    op.drop_index("ix_promotores_metas_evento_promotor_id", table_name="promotores_metas_evento")
    op.drop_table("promotores_metas_evento")
