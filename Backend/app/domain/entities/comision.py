from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.enums import EstadoComision


@dataclass
class Comision:
    id: int | None
    promotor_id: int
    evento_id: int
    porcentaje: Decimal
    monto: Decimal = Decimal("0.00")
    estado: EstadoComision = EstadoComision.PENDIENTE
    fecha_liquidacion: datetime | None = None

    def __post_init__(self) -> None:
        if not (Decimal("0") <= self.porcentaje <= Decimal("100")):
            raise ValueError("El porcentaje de comisión debe estar entre 0 y 100")
        if self.monto < 0:
            raise ValueError("El monto de la comisión no puede ser negativo")
