"""Notificaciones internas y bitácora de movimientos de inventario."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_notif_inventario_mov"
down_revision: Union[str, None] = "0010_whatsapp_bot_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("inventario_items", sa.Column("costo_unitario", sa.Numeric(12, 2), nullable=True))
    op.add_column("inventario_items", sa.Column("proveedor", sa.String(length=100), nullable=True))

    op.create_table(
        "inventario_movimientos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("cantidad", sa.Numeric(12, 2), nullable=False),
        sa.Column("cantidad_anterior", sa.Numeric(12, 2), nullable=False),
        sa.Column("cantidad_nueva", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.String(length=200), nullable=True),
        sa.Column("evento_id", sa.Integer(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('entrada', 'salida', 'consumo', 'ajuste')",
            name="ck_inventario_movimientos_tipo",
        ),
        sa.CheckConstraint("cantidad >= 0", name="ck_inventario_movimientos_cantidad"),
        sa.ForeignKeyConstraint(["item_id"], ["inventario_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventario_movimientos_item_id", "inventario_movimientos", ["item_id"])
    op.create_index("ix_inventario_movimientos_evento_id", "inventario_movimientos", ["evento_id"])
    op.create_index("ix_inventario_movimientos_creado_en", "inventario_movimientos", ["creado_en"])

    op.create_table(
        "notificaciones",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("titulo", sa.String(length=120), nullable=False),
        sa.Column("mensaje", sa.String(length=400), nullable=False),
        sa.Column("nivel", sa.String(length=10), nullable=False, server_default="info"),
        sa.Column("enlace", sa.String(length=200), nullable=True),
        sa.Column("referencia", sa.String(length=60), nullable=True),
        sa.Column("destinatario_rol", sa.String(length=20), nullable=True),
        sa.Column("destinatario_usuario_id", sa.Integer(), nullable=True),
        sa.Column("leida", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("leida_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("nivel IN ('info', 'alerta', 'critica')", name="ck_notificaciones_nivel"),
        sa.ForeignKeyConstraint(["destinatario_usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notificaciones_tipo", "notificaciones", ["tipo"])
    op.create_index("ix_notificaciones_referencia", "notificaciones", ["referencia"])
    op.create_index("ix_notificaciones_destinatario_usuario_id", "notificaciones", ["destinatario_usuario_id"])
    op.create_index("ix_notificaciones_leida_creada", "notificaciones", ["leida", "creada_en"])


def downgrade() -> None:
    op.drop_table("notificaciones")
    op.drop_table("inventario_movimientos")
    op.drop_column("inventario_items", "proveedor")
    op.drop_column("inventario_items", "costo_unitario")
