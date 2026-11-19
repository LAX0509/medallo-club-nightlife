"""Reglas de negocio del inventario: movimientos trazables y vigilancia de existencias."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application import notificacion_service
from app.core.exceptions import ConflictError, NotFoundError
from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.inventario_item_model import InventarioItemModel
from app.infrastructure.models.inventario_movimiento_model import InventarioMovimientoModel
from app.infrastructure.models.notificacion_model import NotificacionModel

CERO = Decimal("0")
TIPOS_STOCK = ("inventario_bajo", "inventario_agotado")


@dataclass
class EstadoStock:
    agotado: bool
    bajo: bool


def estado_de(item: InventarioItemModel) -> EstadoStock:
    return EstadoStock(
        agotado=item.cantidad <= CERO,
        bajo=item.cantidad <= item.stock_minimo,
    )


def _formato(valor: Decimal) -> str:
    return f"{valor:,.2f}".rstrip("0").rstrip(".")


def registrar_movimiento(
    db: Session,
    item: InventarioItemModel,
    *,
    tipo: str,
    cantidad: Decimal,
    motivo: str | None = None,
    evento_id: int | None = None,
    usuario_id: int | None = None,
) -> InventarioMovimientoModel:
    """Aplica un movimiento al ítem y lo deja en la bitácora (sin confirmar la transacción)."""
    anterior = Decimal(item.cantidad)
    if tipo == "entrada":
        nueva = anterior + cantidad
        delta = cantidad
    elif tipo in ("salida", "consumo"):
        if cantidad > anterior:
            raise ConflictError(
                f"No hay existencias suficientes de {item.nombre}: "
                f"disponibles {_formato(anterior)} {item.unidad}."
            )
        nueva = anterior - cantidad
        delta = cantidad
    elif tipo == "ajuste":
        nueva = cantidad
        delta = abs(nueva - anterior)
    else:
        raise ConflictError("Tipo de movimiento no válido.")

    if evento_id is not None and db.get(EventoModel, evento_id) is None:
        raise NotFoundError(f"Evento {evento_id} no encontrado")

    item.cantidad = nueva
    movimiento = InventarioMovimientoModel(
        item_id=item.id,
        tipo=tipo,
        cantidad=delta,
        cantidad_anterior=anterior,
        cantidad_nueva=nueva,
        motivo=motivo,
        evento_id=evento_id,
        usuario_id=usuario_id,
    )
    db.add(movimiento)
    return movimiento


def evaluar_stock(
    db: Session, item: InventarioItemModel, antes: EstadoStock
) -> dict | None:
    """Crea/resuelve notificaciones internas según el cambio de estado del stock.

    Devuelve los datos para el aviso por WhatsApp cuando el ítem acaba de cruzar el
    mínimo (o de agotarse); ``None`` si no hubo un cruce nuevo.
    """
    ahora = estado_de(item)
    referencia = f"inventario:{item.id}"
    unidad = item.unidad

    if not ahora.bajo:
        if antes.bajo:
            # Se repuso: las alertas abiertas de este producto dejan de ser vigentes.
            db.execute(
                NotificacionModel.__table__.update()
                .where(
                    NotificacionModel.referencia == referencia,
                    NotificacionModel.tipo.in_(TIPOS_STOCK),
                    NotificacionModel.leida.is_(False),
                )
                .values(leida=True, leida_en=datetime.now(timezone.utc))
            )
            db.commit()
        return None

    cruzo_a_agotado = ahora.agotado and not antes.agotado
    cruzo_a_bajo = ahora.bajo and not antes.bajo
    if not (cruzo_a_agotado or cruzo_a_bajo):
        return None

    if ahora.agotado:
        notificacion_service.notificar(
            db,
            tipo="inventario_agotado",
            titulo=f"Producto agotado: {item.nombre}",
            mensaje=f"{item.nombre} se quedó sin existencias. Repón lo antes posible.",
            nivel="critica",
            enlace="/inventario",
            referencia=referencia,
        )
    else:
        notificacion_service.notificar(
            db,
            tipo="inventario_bajo",
            titulo=f"Stock bajo: {item.nombre}",
            mensaje=(
                f"Quedan {_formato(Decimal(item.cantidad))} {unidad} y el mínimo es "
                f"{_formato(Decimal(item.stock_minimo))} {unidad}."
            ),
            nivel="alerta",
            enlace="/inventario",
            referencia=referencia,
        )
    return {
        "nombre": item.nombre,
        "cantidad": float(item.cantidad),
        "unidad": unidad,
        "stock_minimo": float(item.stock_minimo),
        "categoria": item.categoria or "General",
    }


def resumen(db: Session) -> dict:
    items = list(db.execute(select(InventarioItemModel)).scalars())
    valor_total = CERO
    categorias: dict[str, dict] = {}
    for item in items:
        valor = Decimal(item.cantidad) * Decimal(item.costo_unitario or 0)
        valor_total += valor
        clave = item.categoria or "Sin categoría"
        fila = categorias.setdefault(clave, {"categoria": clave, "productos": 0, "valor": CERO})
        fila["productos"] += 1
        fila["valor"] += valor

    inicio_hoy = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    movimientos_hoy = db.execute(
        select(func.count())
        .select_from(InventarioMovimientoModel)
        .where(InventarioMovimientoModel.creado_en >= inicio_hoy)
    ).scalar_one()

    hace_7_dias = datetime.now(timezone.utc) - timedelta(days=7)
    consumo = db.execute(
        select(
            InventarioItemModel.id,
            InventarioItemModel.nombre,
            InventarioItemModel.unidad,
            func.sum(InventarioMovimientoModel.cantidad).label("total"),
        )
        .join(InventarioItemModel, InventarioItemModel.id == InventarioMovimientoModel.item_id)
        .where(
            InventarioMovimientoModel.tipo.in_(("consumo", "salida")),
            InventarioMovimientoModel.creado_en >= hace_7_dias,
        )
        .group_by(InventarioItemModel.id, InventarioItemModel.nombre, InventarioItemModel.unidad)
        .order_by(func.sum(InventarioMovimientoModel.cantidad).desc())
        .limit(5)
    ).all()

    return {
        "productos": len(items),
        "en_minimo": sum(1 for i in items if i.cantidad <= i.stock_minimo and i.cantidad > 0),
        "agotados": sum(1 for i in items if i.cantidad <= 0),
        "valor_total": valor_total,
        "movimientos_hoy": int(movimientos_hoy),
        "categorias": sorted(categorias.values(), key=lambda c: c["categoria"]),
        "mayor_consumo_7d": [
            {"item_id": r.id, "nombre": r.nombre, "unidad": r.unidad, "cantidad": Decimal(r.total or 0)}
            for r in consumo
        ],
    }
