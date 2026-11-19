"""Add a private cancellation token to public reservation requests.

Revision ID: 0004_token_cancelacion_reserva
Revises: 0003_eventos_agenda
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_token_cancelacion_reserva"
down_revision: Union[str, None] = "0003_eventos_agenda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reservas",
        sa.Column("token_cancelacion_hash", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_reservas_token_cancelacion_hash", "reservas", ["token_cancelacion_hash"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_reservas_token_cancelacion_hash", "reservas", type_="unique"
    )
    op.drop_column("reservas", "token_cancelacion_hash")
