from pydantic import BaseModel, Field


class MetaPromotorActualizar(BaseModel):
    evento_id: int = Field(gt=0)
    objetivo: int = Field(ge=1, le=10000)


class MetaPromotorRespuesta(BaseModel):
    evento_id: int
    objetivo: int | None


class InvitadosResumenRespuesta(BaseModel):
    total: int
    ingresaron: int
    pendientes: int
