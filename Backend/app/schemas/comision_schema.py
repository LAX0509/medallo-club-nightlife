from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import EstadoComision


class ComisionCrear(BaseModel):
    promotor_id: int = Field(gt=0)
    evento_id: int = Field(gt=0)
    porcentaje: Decimal = Field(ge=0, le=100)


class ComisionActualizar(BaseModel):
    estado: EstadoComision | None = None
    monto: Decimal | None = Field(default=None, ge=0)


class ComisionRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    promotor_id: int
    evento_id: int
    porcentaje: Decimal
    monto: Decimal
    estado: EstadoComision
    fecha_liquidacion: datetime | None
