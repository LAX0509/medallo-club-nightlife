"""Create public table and VIP booth reservation requests.

Revision ID: 0002_create_reservas
Revises: 0001_initial_schema
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_create_reservas"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reservas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("nombre_cliente", sa.String(length=100), nullable=False),
        sa.Column("telefono", sa.String(length=24), nullable=False),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("asistentes", sa.Integer(), nullable=False),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="pendiente", nullable=False),
        sa.Column(
            "fecha_solicitud",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("tipo IN ('mesa', 'palco')", name="ck_reservas_tipo"),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'confirmada', 'cancelada')",
            name="ck_reservas_estado",
        ),
        sa.CheckConstraint("asistentes > 0", name="ck_reservas_asistentes"),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reservas_evento_id", "reservas", ["evento_id"])


def downgrade() -> None:
    op.drop_index("ix_reservas_evento_id", table_name="reservas")
    op.drop_table("reservas")
