"""Alinea los índices únicos de usuarios.email e invitados.qr_code con los modelos.

La migración inicial creó una restricción UNIQUE más un índice normal; los modelos declaran
un único índice UNIQUE. Se reemplaza por el índice único (misma garantía de unicidad) para que
`alembic check` no detecte diferencias. Es defensiva: tolera bases creadas con `create_all`.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0014_alinear_indices_unicos"
down_revision: Union[str, None] = "0013_chat_bot_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS uq_usuarios_email")
    op.execute("DROP INDEX IF EXISTS ix_usuarios_email")
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)

    op.execute("ALTER TABLE invitados DROP CONSTRAINT IF EXISTS uq_invitados_qr_code")
    op.execute("DROP INDEX IF EXISTS ix_invitados_qr_code")
    op.create_index("ix_invitados_qr_code", "invitados", ["qr_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_invitados_qr_code", table_name="invitados")
    op.create_index("ix_invitados_qr_code", "invitados", ["qr_code"], unique=False)
    op.create_unique_constraint("uq_invitados_qr_code", "invitados", ["qr_code"])

    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=False)
    op.create_unique_constraint("uq_usuarios_email", "usuarios", ["email"])
