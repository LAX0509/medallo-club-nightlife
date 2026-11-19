from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InventarioBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    categoria: str | None = Field(default=None, max_length=60)
    cantidad: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    unidad: str = Field(default="unidades", min_length=1, max_length=20)
    stock_minimo: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    costo_unitario: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    precio_venta: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    proveedor: str | None = Field(default=None, max_length=100)

    @field_validator("nombre", "unidad", mode="before")
    @classmethod
    def quitar_espacios_exteriores(cls, valor: str) -> str:
        return valor.strip() if isinstance(valor, str) else valor

    @field_validator("categoria", "proveedor", mode="before")
    @classmethod
    def normalizar_texto_opcional(cls, valor: str | None) -> str | None:
        if isinstance(valor, str):
            return valor.strip() or None
        return valor


class InventarioCrear(InventarioBase):
    pass


class InventarioActualizar(InventarioBase):
    pass


class InventarioRespuesta(InventarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actualizado_en: datetime
    estado_stock: Literal["ok", "bajo", "agotado"] = "ok"
    reposicion_sugerida: Decimal = Decimal("0")

    @model_validator(mode="after")
    def calcular_estado(self) -> "InventarioRespuesta":
        if self.cantidad <= 0:
            self.estado_stock = "agotado"
        elif self.cantidad <= self.stock_minimo:
            self.estado_stock = "bajo"
        else:
            self.estado_stock = "ok"
        objetivo = self.stock_minimo * 2
        self.reposicion_sugerida = max(objetivo - self.cantidad, Decimal("0"))
        return self


TipoMovimiento = Literal["entrada", "salida", "consumo", "ajuste"]


class MovimientoCrear(BaseModel):
    tipo: TipoMovimiento
    # Para entrada/salida/consumo es la cantidad a mover; para ajuste, el conteo físico final.
    cantidad: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    motivo: str | None = Field(default=None, max_length=200)
    evento_id: int | None = Field(default=None, gt=0)

    @field_validator("motivo", mode="before")
    @classmethod
    def limpiar_motivo(cls, valor: str | None) -> str | None:
        return valor.strip() or None if isinstance(valor, str) else valor

    @model_validator(mode="after")
    def validar_cantidad(self) -> "MovimientoCrear":
        if self.tipo != "ajuste" and self.cantidad <= 0:
            raise ValueError("La cantidad del movimiento debe ser mayor que cero.")
        return self


class MovimientoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    item_nombre: str | None = None
    tipo: str
    cantidad: Decimal
    cantidad_anterior: Decimal
    cantidad_nueva: Decimal
    motivo: str | None
    evento_id: int | None
    usuario_id: int | None
    creado_en: datetime


class MovimientoRegistrado(BaseModel):
    item: InventarioRespuesta
    movimiento: MovimientoRespuesta


class CategoriaResumen(BaseModel):
    categoria: str
    productos: int
    valor: Decimal


class ConsumoItem(BaseModel):
    item_id: int
    nombre: str
    unidad: str
    cantidad: Decimal


class InventarioResumen(BaseModel):
    productos: int
    en_minimo: int
    agotados: int
    valor_total: Decimal
    movimientos_hoy: int
    categorias: list[CategoriaResumen]
    mayor_consumo_7d: list[ConsumoItem]
