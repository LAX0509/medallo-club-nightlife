"""Conversaciones del asistente de IA, análisis de sentimientos y configuración del bot."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013_chat_bot_config"
down_revision: Union[str, None] = "0012_reserva_garantizada"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sesiones",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("canal", sa.String(length=10), nullable=False),
        sa.Column("contacto_hash", sa.String(length=64), nullable=True),
        sa.Column("estado_dialogo", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("mensajes_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("negativos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sentimiento_promedio", sa.Numeric(4, 2), nullable=False, server_default="0"),
        sa.Column("escalada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("escalada_resuelta", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reserva_id", sa.Integer(), nullable=True),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actualizada_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("canal IN ('web', 'whatsapp')", name="ck_chat_sesiones_canal"),
        sa.ForeignKeyConstraint(["reserva_id"], ["reservas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_sesiones_contacto_hash", "chat_sesiones", ["contacto_hash"])
    op.create_index("ix_chat_sesiones_actualizada", "chat_sesiones", ["actualizada_en"])

    op.create_table(
        "chat_mensajes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sesion_id", sa.String(length=36), nullable=False),
        sa.Column("autor", sa.String(length=10), nullable=False),
        sa.Column("texto", sa.Text(), nullable=True),
        sa.Column("sentimiento", sa.String(length=20), nullable=True),
        sa.Column("puntaje", sa.Numeric(4, 2), nullable=True),
        sa.Column("emocion", sa.String(length=20), nullable=True),
        sa.Column("aspectos", sa.String(length=200), nullable=True),
        sa.Column("intencion", sa.String(length=30), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("autor IN ('usuario', 'bot')", name="ck_chat_mensajes_autor"),
        sa.ForeignKeyConstraint(["sesion_id"], ["chat_sesiones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_mensajes_sesion_id", "chat_mensajes", ["sesion_id"])
    op.create_index("ix_chat_mensajes_creado_en", "chat_mensajes", ["creado_en"])

    op.create_table(
        "bot_configuracion",
        sa.Column("clave", sa.String(length=60), nullable=False),
        sa.Column("valor", sa.Text(), nullable=False, server_default=""),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("clave"),
    )


def downgrade() -> None:
    op.drop_table("bot_configuracion")
    op.drop_table("chat_mensajes")
    op.drop_table("chat_sesiones")
