from pydantic import BaseModel

from app.schemas.alerta_riesgo_schema import AlertaRiesgoRespuesta


class ResumenEventoRespuesta(BaseModel):
    evento_id: int
    evento_nombre: str
    aforo_maximo: int
    accesos_validos: int
    accesos_duplicados: int
    accesos_rechazados: int
    porcentaje_aforo: float
    comisiones_pendientes: float
    comisiones_liquidadas: float
    alertas_activas: list[AlertaRiesgoRespuesta]
    nivel_riesgo_general: str
    recomendacion: str
