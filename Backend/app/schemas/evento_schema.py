from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import EstadoEvento
from app.schemas.common import ListaPaginada


class EventoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    fecha: date
    aforo_maximo: int = Field(gt=0)
    tematica: str | None = Field(default=None, max_length=240)


class EventoActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    fecha: date | None = None
    aforo_maximo: int | None = Field(default=None, gt=0)
    tematica: str | None = Field(default=None, max_length=240)
    estado: EstadoEvento | None = None


class EventoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    administrador_id: int
    nombre: str
    fecha: date
    aforo_maximo: int
    tematica: str | None = None
    flyer_url: str | None = None
    estado: EstadoEvento


class EventoListaRespuesta(ListaPaginada):
    items: list[EventoRespuesta]
