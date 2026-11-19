import csv
import io
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_roles
from app.application import inventario_service
from app.application.whatsapp_notification_service import notificar_stock_bajo
from app.core.tareas import lanzar
from app.domain.entities.usuario import Usuario
from app.domain.enums import RolUsuario
from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.inventario_item_model import InventarioItemModel
from app.infrastructure.models.inventario_movimiento_model import InventarioMovimientoModel
from app.schemas.inventario_schema import (
    ConsumoItem,
    InventarioActualizar,
    InventarioCrear,
    InventarioResumen,
    InventarioRespuesta,
    MovimientoCrear,
    MovimientoRegistrado,
    MovimientoRespuesta,
)

router = APIRouter(
    prefix="/inventario",
    tags=["Inventario"],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)


def _datos_item(payload: InventarioCrear | InventarioActualizar) -> dict:
    return {
        "nombre": payload.nombre.strip(),
        "categoria": payload.categoria.strip() or None if payload.categoria else None,
        "cantidad": payload.cantidad,
        "unidad": payload.unidad.strip(),
        "stock_minimo": payload.stock_minimo,
        "costo_unitario": payload.costo_unitario,
        "precio_venta": payload.precio_venta,
        "proveedor": payload.proveedor.strip() or None if payload.proveedor else None,
    }


def _movimiento_respuesta(mov: InventarioMovimientoModel, nombre: str | None = None) -> MovimientoRespuesta:
    data = MovimientoRespuesta.model_validate(mov)
    data.item_nombre = nombre
    return data


def _avisar_whatsapp(background_tasks: BackgroundTasks, datos: dict | None) -> None:
    if datos:
        lanzar(background_tasks, notificar_stock_bajo, datos)


def _obtener_item(db: Session, item_id: int) -> InventarioItemModel:
    item = db.get(InventarioItemModel, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Producto de inventario no encontrado.")
    return item


@router.get("", response_model=list[InventarioRespuesta])
def listar_inventario(
    buscar: str | None = Query(default=None, max_length=100),
    categoria: str | None = Query(default=None, max_length=60),
    estado: Literal["ok", "bajo", "agotado"] | None = None,
    db: Session = Depends(get_db),
) -> list[InventarioRespuesta]:
    stmt = select(InventarioItemModel)
    if buscar and buscar.strip():
        stmt = stmt.where(InventarioItemModel.nombre.ilike(f"%{buscar.strip()}%"))
    if categoria and categoria.strip():
        stmt = stmt.where(InventarioItemModel.categoria == categoria.strip())
    stmt = stmt.order_by(InventarioItemModel.nombre.asc(), InventarioItemModel.id.asc())
    items = [InventarioRespuesta.model_validate(item) for item in db.execute(stmt).scalars()]
    if estado:
        items = [item for item in items if item.estado_stock == estado]
    return items


@router.get("/resumen", response_model=InventarioResumen)
def resumen_inventario(db: Session = Depends(get_db)) -> InventarioResumen:
    return InventarioResumen(**inventario_service.resumen(db))


@router.get("/movimientos", response_model=list[MovimientoRespuesta])
def listar_movimientos(
    tipo: Literal["entrada", "salida", "consumo", "ajuste"] | None = None,
    evento_id: int | None = Query(default=None, gt=0),
    limite: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[MovimientoRespuesta]:
    stmt = (
        select(InventarioMovimientoModel, InventarioItemModel.nombre)
        .join(InventarioItemModel, InventarioItemModel.id == InventarioMovimientoModel.item_id)
        .order_by(InventarioMovimientoModel.creado_en.desc(), InventarioMovimientoModel.id.desc())
        .limit(limite)
    )
    if tipo:
        stmt = stmt.where(InventarioMovimientoModel.tipo == tipo)
    if evento_id:
        stmt = stmt.where(InventarioMovimientoModel.evento_id == evento_id)
    return [_movimiento_respuesta(mov, nombre) for mov, nombre in db.execute(stmt).all()]


@router.get("/exportar.csv")
def exportar_inventario_csv(db: Session = Depends(get_db)) -> StreamingResponse:
    items = db.execute(
        select(InventarioItemModel).order_by(InventarioItemModel.nombre.asc())
    ).scalars()
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";")
    escritor.writerow(
        ["Producto", "Categoría", "Existencias", "Unidad", "Mínimo", "Estado",
         "Costo unitario", "Precio de venta", "Valor en stock", "Proveedor", "Reposición sugerida"]
    )
    for item in items:
        datos = InventarioRespuesta.model_validate(item)
        valor = Decimal(datos.cantidad) * Decimal(datos.costo_unitario or 0)
        escritor.writerow([
            datos.nombre, datos.categoria or "", datos.cantidad, datos.unidad, datos.stock_minimo,
            datos.estado_stock, datos.costo_unitario if datos.costo_unitario is not None else "",
            datos.precio_venta if datos.precio_venta is not None else "",
            valor, datos.proveedor or "", datos.reposicion_sugerida,
        ])
    contenido = "﻿" + salida.getvalue()  # BOM para que Excel reconozca los acentos
    return StreamingResponse(
        iter([contenido]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="inventario-medallo-club.csv"'},
    )


@router.get("/eventos/{evento_id}/consumo", response_model=list[ConsumoItem])
def consumo_por_evento(evento_id: int, db: Session = Depends(get_db)) -> list[ConsumoItem]:
    if db.get(EventoModel, evento_id) is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    filas = db.execute(
        select(
            InventarioItemModel.id,
            InventarioItemModel.nombre,
            InventarioItemModel.unidad,
            func.sum(InventarioMovimientoModel.cantidad),
        )
        .join(InventarioItemModel, InventarioItemModel.id == InventarioMovimientoModel.item_id)
        .where(
            InventarioMovimientoModel.evento_id == evento_id,
            InventarioMovimientoModel.tipo.in_(("consumo", "salida")),
        )
        .group_by(InventarioItemModel.id, InventarioItemModel.nombre, InventarioItemModel.unidad)
        .order_by(InventarioItemModel.nombre.asc())
    ).all()
    return [
        ConsumoItem(item_id=i, nombre=n, unidad=u, cantidad=Decimal(total or 0))
        for i, n, u, total in filas
    ]


@router.post("", response_model=InventarioRespuesta, status_code=status.HTTP_201_CREATED)
def crear_item_inventario(
    payload: InventarioCrear,
    background_tasks: BackgroundTasks,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventarioRespuesta:
    datos = _datos_item(payload)
    cantidad_inicial = datos["cantidad"]
    item = InventarioItemModel(**{**datos, "cantidad": 0})
    db.add(item)
    db.flush()
    if cantidad_inicial > 0:
        inventario_service.registrar_movimiento(
            db, item, tipo="entrada", cantidad=cantidad_inicial,
            motivo="Existencias iniciales", usuario_id=usuario.id,
        )
    db.commit()
    db.refresh(item)
    # Un producto nuevo ya nace "en mínimo" si arranca por debajo: se avisa de inmediato.
    _avisar_whatsapp(
        background_tasks,
        inventario_service.evaluar_stock(db, item, inventario_service.EstadoStock(False, False)),
    )
    return InventarioRespuesta.model_validate(item)


@router.put("/{item_id}", response_model=InventarioRespuesta)
def actualizar_item_inventario(
    item_id: int,
    payload: InventarioActualizar,
    background_tasks: BackgroundTasks,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventarioRespuesta:
    item = _obtener_item(db, item_id)
    antes = inventario_service.estado_de(item)
    datos = _datos_item(payload)
    nueva_cantidad = datos.pop("cantidad")
    for campo, valor in datos.items():
        setattr(item, campo, valor)
    if Decimal(item.cantidad) != nueva_cantidad:
        inventario_service.registrar_movimiento(
            db, item, tipo="ajuste", cantidad=nueva_cantidad,
            motivo="Edición manual del producto", usuario_id=usuario.id,
        )
    db.commit()
    db.refresh(item)
    _avisar_whatsapp(background_tasks, inventario_service.evaluar_stock(db, item, antes))
    return InventarioRespuesta.model_validate(item)


@router.post(
    "/{item_id}/movimientos",
    response_model=MovimientoRegistrado,
    status_code=status.HTTP_201_CREATED,
)
def registrar_movimiento_inventario(
    item_id: int,
    payload: MovimientoCrear,
    background_tasks: BackgroundTasks,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MovimientoRegistrado:
    item = _obtener_item(db, item_id)
    antes = inventario_service.estado_de(item)
    movimiento = inventario_service.registrar_movimiento(
        db,
        item,
        tipo=payload.tipo,
        cantidad=payload.cantidad,
        motivo=payload.motivo,
        evento_id=payload.evento_id,
        usuario_id=usuario.id,
    )
    db.commit()
    db.refresh(item)
    db.refresh(movimiento)
    _avisar_whatsapp(background_tasks, inventario_service.evaluar_stock(db, item, antes))
    return MovimientoRegistrado(
        item=InventarioRespuesta.model_validate(item),
        movimiento=_movimiento_respuesta(movimiento, item.nombre),
    )


@router.get("/{item_id}/movimientos", response_model=list[MovimientoRespuesta])
def historial_item(
    item_id: int,
    limite: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[MovimientoRespuesta]:
    item = _obtener_item(db, item_id)
    stmt = (
        select(InventarioMovimientoModel)
        .where(InventarioMovimientoModel.item_id == item_id)
        .order_by(InventarioMovimientoModel.creado_en.desc(), InventarioMovimientoModel.id.desc())
        .limit(limite)
    )
    return [_movimiento_respuesta(m, item.nombre) for m in db.execute(stmt).scalars()]


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_item_inventario(item_id: int, db: Session = Depends(get_db)) -> None:
    item = _obtener_item(db, item_id)
    db.delete(item)
    db.commit()
