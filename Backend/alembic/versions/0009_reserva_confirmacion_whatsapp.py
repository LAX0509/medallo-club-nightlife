"""Track WhatsApp confirmation delivery attempts for reservations."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_reserva_whatsapp"
down_revision: Union[str, None] = "0008_inventario_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("reservas", sa.Column("whatsapp_confirmacion_estado", sa.String(length=20), server_default="sin_configurar", nullable=False))
    op.add_column("reservas", sa.Column("whatsapp_confirmacion_error", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("reservas", "whatsapp_confirmacion_error")
    op.drop_column("reservas", "whatsapp_confirmacion_estado")
