from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import EstadoInvitado
from app.schemas.common import ListaPaginada


class InvitadoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    evento_id: int = Field(gt=0)
    promotor_id: int = Field(gt=0)


class InvitadoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evento_id: int
    promotor_id: int
    nombre: str
    qr_code: str
    estado: EstadoInvitado
    fecha_registro: datetime | None


class InvitadoListaRespuesta(ListaPaginada):
    items: list[InvitadoRespuesta]
