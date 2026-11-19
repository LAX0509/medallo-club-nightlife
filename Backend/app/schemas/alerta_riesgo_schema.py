from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import EstadoAlerta, NivelAlerta, TipoAlerta


class AlertaRiesgoActualizar(BaseModel):
    estado: EstadoAlerta


class AlertaRiesgoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evento_id: int
    tipo_alerta: TipoAlerta
    nivel: NivelAlerta
    descripcion: str
    estado: EstadoAlerta
    fecha_hora: datetime | None


class AlertaRiesgoListaRespuesta(BaseModel):
    items: list[AlertaRiesgoRespuesta]
    total: int
