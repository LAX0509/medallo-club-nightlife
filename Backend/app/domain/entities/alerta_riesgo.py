from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import EstadoAlerta, NivelAlerta, TipoAlerta


@dataclass
class AlertaRiesgo:
    id: int | None
    evento_id: int
    tipo_alerta: TipoAlerta
    nivel: NivelAlerta
    descripcion: str
    estado: EstadoAlerta = EstadoAlerta.ACTIVA
    fecha_hora: datetime | None = None
