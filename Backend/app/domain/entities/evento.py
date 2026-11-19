from dataclasses import dataclass
from datetime import date

from app.domain.enums import EstadoEvento


@dataclass
class Evento:
    id: int | None
    administrador_id: int
    nombre: str
    fecha: date
    aforo_maximo: int
    tematica: str | None = None
    flyer_url: str | None = None
    estado: EstadoEvento = EstadoEvento.PLANEADO

    def __post_init__(self) -> None:
        if self.aforo_maximo <= 0:
            raise ValueError("El aforo máximo debe ser un entero mayor a cero")
