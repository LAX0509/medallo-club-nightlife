import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TipoReserva(str, Enum):
    MESA = "mesa"
    PALCO = "palco"


class EstadoReserva(str, Enum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"


class ReservaCrear(BaseModel):
    evento_id: int = Field(gt=0)
    promotor_id: int | None = Field(default=None, gt=0)
    nombre_cliente: str = Field(min_length=2, max_length=100)
    telefono: str = Field(min_length=7, max_length=24, pattern=r"^[0-9+()\-\s]+$")
    tipo: TipoReserva
    asistentes: int = Field(ge=1, le=50)
    notas: str | None = Field(default=None, max_length=500)


class ReservaEstadoActualizar(BaseModel):
    estado: EstadoReserva
    # Condiciones de la garantía; solo se usan al confirmar.
    ubicacion_asignada: str | None = Field(default=None, max_length=60)
    hora_limite: str | None = Field(default=None, description="Formato HH:MM (24 h)")
    consumo_minimo: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    forzar_cupo: bool = False

    @field_validator("hora_limite")
    @classmethod
    def validar_hora(cls, valor: str | None) -> str | None:
        if valor is None or not valor.strip():
            return None
        valor = valor.strip()
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", valor):
            raise ValueError("La hora límite debe tener formato HH:MM (24 horas).")
        return valor

    @field_validator("ubicacion_asignada", mode="before")
    @classmethod
    def limpiar_ubicacion(cls, valor: str | None) -> str | None:
        return valor.strip() or None if isinstance(valor, str) else valor


class ReservaCancelar(BaseModel):
    token_cancelacion: str = Field(min_length=32, max_length=128)


class EventoReservaRespuesta(BaseModel):
    id: int
    nombre: str
    fecha: date
    tematica: str | None = None
    flyer_url: str | None = None


class ReservaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evento_id: int
    promotor_id: int | None = None
    promotor_nombre: str | None = None
    evento_nombre: str
    nombre_cliente: str
    telefono: str
    tipo: TipoReserva
    asistentes: int
    notas: str | None
    estado: EstadoReserva
    whatsapp_confirmacion_estado: str = "sin_configurar"
    whatsapp_confirmacion_error: str | None = None
    fecha_solicitud: datetime
    # Reserva garantizada
    garantizada: bool = False
    codigo_garantia: str | None = None
    garantizada_en: datetime | None = None
    hora_limite: str | None = None
    ubicacion_asignada: str | None = None
    consumo_minimo: Decimal | None = None
    pases_total: int = 0
    pases_usados: int = 0


class ReservaCreadaRespuesta(ReservaRespuesta):
    # Se devuelve únicamente al crear la solicitud. Nunca se incluye en los
    # endpoints administrativos; la base de datos conserva solo su hash.
    token_cancelacion: str


class PaseReservaRespuesta(BaseModel):
    id: int
    nombre: str
    qr_code: str
    estado: str


class ConsultaReservaCliente(BaseModel):
    token_cancelacion: str = Field(min_length=32, max_length=128)


class ReservaClienteRespuesta(BaseModel):
    """Vista privada del cliente (acceso por token): estado, garantía y pases."""

    id: int
    estado: EstadoReserva
    tipo: TipoReserva
    asistentes: int
    nombre_cliente: str
    evento_nombre: str
    evento_fecha: date
    evento_tematica: str | None = None
    flyer_url: str | None = None
    garantizada: bool
    codigo_garantia: str | None = None
    hora_limite: str | None = None
    ubicacion_asignada: str | None = None
    consumo_minimo: Decimal | None = None
    pases: list[PaseReservaRespuesta] = []
    puede_cancelar: bool = False
