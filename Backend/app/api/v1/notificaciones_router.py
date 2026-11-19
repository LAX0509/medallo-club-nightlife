from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.application import notificacion_service
from app.domain.entities.usuario import Usuario

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


class NotificacionRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    titulo: str
    mensaje: str
    nivel: str
    enlace: str | None
    leida: bool
    creada_en: datetime


class ResumenNotificaciones(BaseModel):
    no_leidas: int
    items: list[NotificacionRespuesta]


@router.get("", response_model=ResumenNotificaciones)
def listar_notificaciones(
    solo_no_leidas: bool = False,
    limite: int = Query(default=30, ge=1, le=100),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumenNotificaciones:
    items = notificacion_service.listar(db, usuario, solo_no_leidas=solo_no_leidas, limite=limite)
    return ResumenNotificaciones(
        no_leidas=notificacion_service.contar_no_leidas(db, usuario),
        items=[NotificacionRespuesta.model_validate(item) for item in items],
    )


@router.post("/leer-todas")
def marcar_todas(
    usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, int]:
    return {"marcadas": notificacion_service.marcar_todas_leidas(db, usuario)}


@router.post("/{notificacion_id}/leer")
def marcar_una(
    notificacion_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    if not notificacion_service.marcar_leida(db, usuario, notificacion_id):
        raise HTTPException(status_code=404, detail="Notificación no encontrada.")
    return {"leida": True}
