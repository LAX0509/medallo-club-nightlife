from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import ResultadoAcceso, TipoAcceso


@dataclass
class AccesoQR:
    id: int | None
    evento_id: int
    tipo: TipoAcceso
    resultado: ResultadoAcceso
    invitado_id: int | None = None
    justificacion: str | None = None
    fecha_hora: datetime | None = None
