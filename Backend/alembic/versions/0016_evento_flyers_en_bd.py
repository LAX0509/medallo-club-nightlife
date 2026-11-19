"""Flyers de eventos guardados en la base de datos (el hosting sin servidor no permite escribir en disco)."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016_evento_flyers_en_bd"
down_revision: Union[str, None] = "0015_whatsapp_estados"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evento_flyers",
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("subida", sa.String(length=36), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("evento_id"),
    )
    op.create_table(
        "evento_flyer_partes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("subida", sa.String(length=36), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("datos", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evento_id", "subida", "orden", name="uq_evento_flyer_partes_orden"),
    )
    op.create_index("ix_evento_flyer_partes_evento_subida", "evento_flyer_partes", ["evento_id", "subida"])


def downgrade() -> None:
    op.drop_index("ix_evento_flyer_partes_evento_subida", table_name="evento_flyer_partes")
    op.drop_table("evento_flyer_partes")
    op.drop_table("evento_flyers")
