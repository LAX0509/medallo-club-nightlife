"""Add WhatsApp bot message analytics and delivery tracking."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_whatsapp_bot_webhooks"
down_revision: Union[str, None] = "0009_reserva_whatsapp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reservas",
        sa.Column("whatsapp_confirmacion_message_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_reservas_whatsapp_confirmacion_message_id",
        "reservas",
        ["whatsapp_confirmacion_message_id"],
        unique=False,
    )
    op.create_table(
        "whatsapp_inbound_messages",
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("sender_hash", sa.String(length=64), nullable=False),
        sa.Column("sentiment", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("response_status", sa.String(length=20), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        "ix_whatsapp_inbound_received_at",
        "whatsapp_inbound_messages",
        ["received_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_whatsapp_inbound_received_at", table_name="whatsapp_inbound_messages")
    op.drop_table("whatsapp_inbound_messages")
    op.drop_index("ix_reservas_whatsapp_confirmacion_message_id", table_name="reservas")
    op.drop_column("reservas", "whatsapp_confirmacion_message_id")
