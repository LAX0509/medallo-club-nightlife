"""Add theme and flyer to event agenda.

Revision ID: 0003_eventos_agenda
Revises: 0002_create_reservas
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_eventos_agenda"
down_revision: Union[str, None] = "0002_create_reservas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("eventos", sa.Column("tematica", sa.String(length=240), nullable=True))
    op.add_column("eventos", sa.Column("flyer_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("eventos", "flyer_url")
    op.drop_column("eventos", "tematica")
