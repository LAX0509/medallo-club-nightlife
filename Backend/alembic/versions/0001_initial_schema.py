"""Esquema inicial: usuarios, eventos, invitados, comisiones, accesos_qr, alertas_riesgo

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("rol", sa.String(length=20), nullable=False),
        sa.Column("telefono", sa.String(length=20), nullable=True),
        sa.Column("estado", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "fecha_registro",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rol IN ('Administrador', 'Promotor', 'Puerta')", name="ck_usuarios_rol"
        ),
        sa.UniqueConstraint("email", name="uq_usuarios_email"),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"])

    op.create_table(
        "eventos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "administrador_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("aforo_maximo", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="planeado"),
        sa.CheckConstraint("aforo_maximo > 0", name="ck_eventos_aforo_positivo"),
        sa.CheckConstraint(
            "estado IN ('planeado', 'en curso', 'cerrado')", name="ck_eventos_estado"
        ),
    )
    op.create_index("ix_eventos_administrador_id", "eventos", ["administrador_id"])

    op.create_table(
        "invitados",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "evento_id",
            sa.Integer(),
            sa.ForeignKey("eventos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "promotor_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("qr_code", sa.String(length=255), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="pendiente"),
        sa.Column(
            "fecha_registro",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("estado IN ('pendiente', 'usado')", name="ck_invitados_estado"),
        sa.UniqueConstraint("qr_code", name="uq_invitados_qr_code"),
    )
    op.create_index("ix_invitados_evento_id", "invitados", ["evento_id"])
    op.create_index("ix_invitados_promotor_id", "invitados", ["promotor_id"])
    op.create_index("ix_invitados_qr_code", "invitados", ["qr_code"])

    op.create_table(
        "comisiones",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "promotor_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "evento_id",
            sa.Integer(),
            sa.ForeignKey("eventos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("porcentaje", sa.Numeric(5, 2), nullable=False),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="pendiente"),
        sa.Column("fecha_liquidacion", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "porcentaje >= 0 AND porcentaje <= 100", name="ck_comisiones_porcentaje"
        ),
        sa.CheckConstraint("monto >= 0", name="ck_comisiones_monto_no_negativo"),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'liquidada')", name="ck_comisiones_estado"
        ),
    )
    op.create_index("ix_comisiones_promotor_id", "comisiones", ["promotor_id"])
    op.create_index("ix_comisiones_evento_id", "comisiones", ["evento_id"])

    op.create_table(
        "accesos_qr",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "invitado_id",
            sa.Integer(),
            sa.ForeignKey("invitados.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "evento_id",
            sa.Integer(),
            sa.ForeignKey("eventos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("resultado", sa.String(length=20), nullable=False),
        sa.Column("justificacion", sa.Text(), nullable=True),
        sa.Column(
            "fecha_hora",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("tipo IN ('qr', 'cortesia_manual')", name="ck_accesos_qr_tipo"),
        sa.CheckConstraint(
            "resultado IN ('valido', 'duplicado', 'rechazado')",
            name="ck_accesos_qr_resultado",
        ),
    )
    op.create_index("ix_accesos_qr_invitado_id", "accesos_qr", ["invitado_id"])
    op.create_index("ix_accesos_qr_evento_id", "accesos_qr", ["evento_id"])
    op.create_index("ix_accesos_qr_fecha_hora", "accesos_qr", ["fecha_hora"])

    op.create_table(
        "alertas_riesgo",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "evento_id",
            sa.Integer(),
            sa.ForeignKey("eventos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo_alerta", sa.String(length=50), nullable=False),
        sa.Column("nivel", sa.String(length=20), nullable=False),
        sa.Column("descripcion", sa.String(length=255), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="activa"),
        sa.Column(
            "fecha_hora",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo_alerta IN ('sobreaforo', 'comision_atipica', 'cortesia_duplicada')",
            name="ck_alertas_tipo",
        ),
        sa.CheckConstraint("nivel IN ('bajo', 'medio', 'alto')", name="ck_alertas_nivel"),
        sa.CheckConstraint("estado IN ('activa', 'resuelta')", name="ck_alertas_estado"),
    )
    op.create_index("ix_alertas_riesgo_evento_id", "alertas_riesgo", ["evento_id"])
    op.create_index("ix_alertas_riesgo_nivel", "alertas_riesgo", ["nivel"])
    op.create_index("ix_alertas_riesgo_fecha_hora", "alertas_riesgo", ["fecha_hora"])


def downgrade() -> None:
    op.drop_table("alertas_riesgo")
    op.drop_table("accesos_qr")
    op.drop_table("comisiones")
    op.drop_table("invitados")
    op.drop_table("eventos")
    op.drop_table("usuarios")
