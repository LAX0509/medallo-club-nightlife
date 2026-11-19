from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, require_roles
from app.domain.entities.usuario import Usuario
from app.domain.enums import RolUsuario
from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.promotor_meta_model import PromotorMetaModel
from app.schemas.promotor_schema import MetaPromotorActualizar, MetaPromotorRespuesta

router = APIRouter(prefix="/promotores", tags=["Funciones del promotor"])


@router.get("/me/meta", response_model=MetaPromotorRespuesta)
def obtener_meta(
    evento_id: int = Query(gt=0),
    usuario: Usuario = Depends(require_roles(RolUsuario.PROMOTOR)),
    db: Session = Depends(get_db),
) -> MetaPromotorRespuesta:
    meta = db.execute(
        select(PromotorMetaModel).where(
            PromotorMetaModel.promotor_id == usuario.id,
            PromotorMetaModel.evento_id == evento_id,
        )
    ).scalar_one_or_none()
    return MetaPromotorRespuesta(evento_id=evento_id, objetivo=meta.objetivo if meta else None)


@router.put("/me/meta", response_model=MetaPromotorRespuesta)
def guardar_meta(
    payload: MetaPromotorActualizar,
    usuario: Usuario = Depends(require_roles(RolUsuario.PROMOTOR)),
    db: Session = Depends(get_db),
) -> MetaPromotorRespuesta:
    evento = db.get(EventoModel, payload.evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")

    meta = db.execute(
        select(PromotorMetaModel).where(
            PromotorMetaModel.promotor_id == usuario.id,
            PromotorMetaModel.evento_id == payload.evento_id,
        )
    ).scalar_one_or_none()
    if meta is None:
        meta = PromotorMetaModel(
            promotor_id=usuario.id,
            evento_id=payload.evento_id,
            objetivo=payload.objetivo,
        )
        db.add(meta)
    else:
        meta.objetivo = payload.objetivo
    db.commit()
    return MetaPromotorRespuesta(evento_id=payload.evento_id, objetivo=payload.objetivo)
