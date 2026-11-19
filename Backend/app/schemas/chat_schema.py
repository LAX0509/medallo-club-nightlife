from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class ChatEntrada(BaseModel):
    sesion_id: str | None = Field(default=None, max_length=36)
    texto: str | None = Field(default=None, max_length=600)
    accion: str | None = Field(default=None, max_length=60)
    # Referido por un promotor (enlace personal); solo se usa al crear la sesión.
    promotor_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def requiere_contenido(self) -> "ChatEntrada":
        if self.texto is not None:
            self.texto = self.texto.strip() or None
        if not self.texto and not self.accion:
            raise ValueError("Escribe un mensaje o elige una opción.")
        return self


class OpcionSalida(BaseModel):
    label: str
    valor: str


class TarjetaEventoSalida(BaseModel):
    id: int
    nombre: str
    fecha: date
    fecha_texto: str
    tematica: str | None = None
    flyer_url: str | None = None


class MensajeSalida(BaseModel):
    texto: str
    opciones: list[OpcionSalida] = []
    eventos: list[TarjetaEventoSalida] = []


class AspectoSalida(BaseModel):
    aspecto: str
    nombre: str | None = None
    sentimiento: str


class AnalisisSalida(BaseModel):
    etiqueta: str
    puntaje: float
    emocion: str
    intensidad: str = "baja"
    aspectos: list[AspectoSalida] = []
    urgente: bool = False


class ReservaChatSalida(BaseModel):
    id: int
    estado: str
    evento_nombre: str
    token_cancelacion: str | None = None
    url_gestion: str | None = None
    simulada: bool = False


class ChatRespuesta(BaseModel):
    sesion_id: str
    mensajes: list[MensajeSalida]
    analisis: AnalisisSalida | None = None
    ia_usada: bool = False
    escalada: bool = False
    reserva: ReservaChatSalida | None = None


class ChatEstadoPublico(BaseModel):
    activo: bool
    ia: bool
    nombre_bot: str
    saludo: str


class ChatHistorialItem(BaseModel):
    autor: str
    texto: str
    creado_en: datetime


class ChatHistorial(BaseModel):
    sesion_id: str
    mensajes: list[ChatHistorialItem]
    opciones: list[OpcionSalida]
    paso: str
    reserva_id: int | None = None
