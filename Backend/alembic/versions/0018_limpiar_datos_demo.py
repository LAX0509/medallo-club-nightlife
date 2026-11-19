"""Retira los datos de demostración que sembró scripts/seed_demo.py (eventos, reservas, invitados, chats e inventario).

Se identifican de forma exacta (nombre del evento, id fijo de cada conversación y producto con el mismo
nombre, costo y proveedor del catálogo de ejemplo), así que lo que el equipo haya creado o editado se conserva.
Los usuarios no se tocan. Las claves foráneas borran en cascada invitados, reservas, accesos, comisiones,
alertas, flyers y movimientos asociados.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018_limpiar_datos_demo"
down_revision: Union[str, None] = "0017_inventario_precio_venta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EVENTOS_DEMO = ("Noche Retro (cerrada)", "Noche Retro Viernes", "Reggaeton Night", "Electro Sunset")
PRODUCTOS_DEMO = [
    ("Aguardiente Antioqueño", 78000, "Fábrica de Licores de Antioquia"),
    ("Ron Medellín", 95000, "Distribuidora Aburrá"),
    ("Whisky Etiqueta Negra", 180000, "Distribuidora Aburrá"),
    ("Vodka", 88000, "Distribuidora Aburrá"),
    ("Champaña", 210000, "Importadora Paisa"),
    ("Cerveza Club Colombia", 4200, "Bavaria"),
    ("Agua sin gas", 1800, "Postobón"),
    ("Gaseosas variadas", 2100, "Postobón"),
    ("Hielo", 5500, "Hielos del Valle"),
    ("Limones", 6000, "Plaza Minorista"),
    ("Vasos desechables", 250, "Empaques SAS"),
    ("Servilletas", 3200, "Empaques SAS"),
]
CONVERSACIONES_DEMO = 27  # len(CONVERSACIONES) del seed


def upgrade() -> None:
    conexion = op.get_bind()
    conexion.execute(sa.text("DELETE FROM eventos WHERE nombre IN :nombres").bindparams(
        sa.bindparam("nombres", expanding=True, value=list(EVENTOS_DEMO))
    ))
    ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"medallo-demo-{i}")) for i in range(CONVERSACIONES_DEMO)]
    conexion.execute(sa.text("DELETE FROM chat_sesiones WHERE id IN :ids").bindparams(
        sa.bindparam("ids", expanding=True, value=ids)
    ))
    for nombre, costo, proveedor in PRODUCTOS_DEMO:
        conexion.execute(
            sa.text("DELETE FROM inventario_items WHERE nombre = :n AND costo_unitario = :c AND proveedor = :p"),
            {"n": nombre, "c": costo, "p": proveedor},
        )


def downgrade() -> None:
    """Los datos de demostración no se restauran (se vuelven a crear con scripts.seed_demo si hace falta)."""
