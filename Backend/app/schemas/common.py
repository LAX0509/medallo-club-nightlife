from pydantic import BaseModel


class MensajeRespuesta(BaseModel):
    mensaje: str


class ListaPaginada(BaseModel):
    total: int
    page: int
    limit: int
