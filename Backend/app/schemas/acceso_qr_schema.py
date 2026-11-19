from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import ResultadoAcceso, TipoAcceso
from app.application.qr_format import normalizar_codigo_qr
from app.schemas.alerta_riesgo_schema import AlertaRiesgoRespuesta
from app.schemas.common import ListaPaginada


class AccesoQRCrear(BaseModel):
    evento_id: int = Field(gt=0)
    qr_code: str | None = Field(default=None, min_length=1, max_length=255)
    tipo: TipoAcceso = TipoAcceso.QR
    nombre_cortesia: str | None = Field(default=None, max_length=100)
    justificacion: str | None = Field(default=None, max_length=500)

    @field_validator("qr_code", mode="before")
    @classmethod
    def normalizar_formato_qr(cls, valor: str | None) -> str | None:
        return normalizar_codigo_qr(valor) if valor is not None else None

    @model_validator(mode="after")
    def validar_segun_tipo(self) -> "AccesoQRCrear":
        if self.tipo == TipoAcceso.QR and not self.qr_code:
            raise ValueError("qr_code es requerido para accesos de tipo QR")
        if self.tipo == TipoAcceso.CORTESIA_MANUAL:
            if not self.justificacion:
                raise ValueError(
                    "La justificación es obligatoria para registrar una cortesía manual"
                )
            if not self.nombre_cortesia:
                raise ValueError(
                    "El nombre del invitado es obligatorio para una cortesía manual"
                )
        return self


class AccesoQRActualizar(BaseModel):
    estado: ResultadoAcceso


class AccesoQRRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evento_id: int
    invitado_id: int | None
    tipo: TipoAcceso
    resultado: ResultadoAcceso
    justificacion: str | None
    fecha_hora: datetime | None


class AccesoQRListaRespuesta(ListaPaginada):
    items: list[AccesoQRRespuesta]


class AccesoQRRegistradoRespuesta(BaseModel):
    acceso: AccesoQRRespuesta
    aforo_actual: int
    aforo_maximo: int
    porcentaje_aforo: float
    alertas_generadas: list[AlertaRiesgoRespuesta] = []


class ResumenPuertaRespuesta(BaseModel):
    evento_id: int
    evento_nombre: str
    aforo_maximo: int
    accesos_validos: int
    accesos_duplicados: int
    accesos_rechazados: int
    porcentaje_aforo: float


class IncidenciaPuertaCrear(BaseModel):
    evento_id: int = Field(gt=0)
    tipo: Literal["qr_duplicado", "qr_rechazado", "nombre_diferente", "otra"]
    persona: str | None = Field(default=None, max_length=100)
    descripcion: str = Field(min_length=3, max_length=500)

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Describe la incidencia con al menos 3 caracteres.")
        return value

    @field_validator("persona")
    @classmethod
    def limpiar_persona(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None


class IncidenciaPuertaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evento_id: int
    usuario_id: int | None
    tipo: str
    persona: str | None
    descripcion: str
    fecha_hora: datetime
