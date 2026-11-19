"""Estados de entrega de WhatsApp reportados por el webhook de Meta (diagnóstico de notificaciones)."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0015_whatsapp_estados"
down_revision: Union[str, None] = "0014_alinear_indices_unicos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_estados",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("destinatario_fin", sa.String(length=8), nullable=True),
        sa.Column("codigo_error", sa.String(length=20), nullable=True),
        sa.Column("titulo_error", sa.String(length=300), nullable=True),
        sa.Column("detalle_error", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whatsapp_estados_message_id", "whatsapp_estados", ["message_id"])
    op.create_index("ix_whatsapp_estados_creado_en", "whatsapp_estados", ["creado_en"])


def downgrade() -> None:
    op.drop_index("ix_whatsapp_estados_creado_en", table_name="whatsapp_estados")
    op.drop_index("ix_whatsapp_estados_message_id", table_name="whatsapp_estados")
    op.drop_table("whatsapp_estados")
