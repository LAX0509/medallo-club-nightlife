"""Store door staff incident reports."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_incidencias_puerta"
down_revision: Union[str, None] = "0006_atribucion_reserva_promotor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incidencias_puerta",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(length=24), nullable=False),
        sa.Column("persona", sa.String(length=100), nullable=True),
        sa.Column("descripcion", sa.String(length=500), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('qr_duplicado', 'qr_rechazado', 'nombre_diferente', 'otra')",
            name="ck_incidencias_puerta_tipo",
        ),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidencias_puerta_evento_id", "incidencias_puerta", ["evento_id"])
    op.create_index("ix_incidencias_puerta_usuario_id", "incidencias_puerta", ["usuario_id"])
    op.create_index("ix_incidencias_puerta_fecha_hora", "incidencias_puerta", ["fecha_hora"])


def downgrade() -> None:
    op.drop_index("ix_incidencias_puerta_fecha_hora", table_name="incidencias_puerta")
    op.drop_index("ix_incidencias_puerta_usuario_id", table_name="incidencias_puerta")
    op.drop_index("ix_incidencias_puerta_evento_id", table_name="incidencias_puerta")
    op.drop_table("incidencias_puerta")
