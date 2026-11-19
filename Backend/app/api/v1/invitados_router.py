from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, get_invitado_service, require_roles
from app.application.invitado_service import InvitadoService
from app.domain.entities.usuario import Usuario
from app.domain.enums import RolUsuario
from app.infrastructure.models.invitado_model import InvitadoModel
from app.schemas.invitado_schema import (
    InvitadoCrear,
    InvitadoListaRespuesta,
    InvitadoRespuesta,
)
from app.schemas.promotor_schema import InvitadosResumenRespuesta

router = APIRouter(prefix="/invitados", tags=["Listas de invitados"])


@router.get("/resumen", response_model=InvitadosResumenRespuesta)
def resumen_invitados(
    evento_id: int = Query(gt=0),
    promotor_id: int | None = Query(default=None, gt=0),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitadosResumenRespuesta:
    filtros = [InvitadoModel.evento_id == evento_id]
    if usuario.rol == RolUsuario.PROMOTOR:
        promotor_id = usuario.id
    if promotor_id is not None:
        filtros.append(InvitadoModel.promotor_id == promotor_id)

    total = db.scalar(
        select(func.count(InvitadoModel.id)).where(*filtros)
    ) or 0
    ingresaron = db.scalar(
        select(func.count(InvitadoModel.id)).where(
            *filtros, InvitadoModel.estado == "usado"
        )
    ) or 0
    return InvitadosResumenRespuesta(
        total=total,
        ingresaron=ingresaron,
        pendientes=total - ingresaron,
    )


@router.get("", response_model=InvitadoListaRespuesta)
def listar_invitados(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    evento_id: int | None = None,
    promotor_id: int | None = None,
    usuario: Usuario = Depends(get_current_user),
    invitado_service: InvitadoService = Depends(get_invitado_service),
) -> InvitadoListaRespuesta:
    # Un Promotor sólo puede ver sus propias listas, sin importar el filtro
    # que envíe: evita fugas de información entre promotores.
    if usuario.rol == RolUsuario.PROMOTOR:
        promotor_id = usuario.id

    invitados, total = invitado_service.listar(
        page=page, limit=limit, evento_id=evento_id, promotor_id=promotor_id
    )
    return InvitadoListaRespuesta(
        items=[InvitadoRespuesta.model_validate(i) for i in invitados],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{invitado_id}",
    response_model=InvitadoRespuesta,
    dependencies=[Depends(get_current_user)],
)
def obtener_invitado(
    invitado_id: int,
    usuario: Usuario = Depends(get_current_user),
    invitado_service: InvitadoService = Depends(get_invitado_service),
) -> InvitadoRespuesta:
    invitado = invitado_service.obtener(invitado_id)
    if usuario.rol == RolUsuario.PROMOTOR and invitado.promotor_id != usuario.id:
        raise HTTPException(status_code=404, detail="Invitado no encontrado")
    return InvitadoRespuesta.model_validate(invitado)


@router.post(
    "",
    response_model=InvitadoRespuesta,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR, RolUsuario.PROMOTOR))],
)
def registrar_invitado(
    payload: InvitadoCrear,
    usuario: Usuario = Depends(get_current_user),
    invitado_service: InvitadoService = Depends(get_invitado_service),
) -> InvitadoRespuesta:
    # Un Promotor sólo puede registrar invitados a su propio nombre.
    promotor_id = usuario.id if usuario.rol == RolUsuario.PROMOTOR else payload.promotor_id
    invitado = invitado_service.registrar(
        nombre=payload.nombre, evento_id=payload.evento_id, promotor_id=promotor_id
    )
    return InvitadoRespuesta.model_validate(invitado)


@router.delete(
    "/{invitado_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR, RolUsuario.PROMOTOR))],
)
def eliminar_invitado(
    invitado_id: int,
    usuario: Usuario = Depends(get_current_user),
    invitado_service: InvitadoService = Depends(get_invitado_service),
) -> None:
    invitado = invitado_service.obtener(invitado_id)
    if usuario.rol == RolUsuario.PROMOTOR and invitado.promotor_id != usuario.id:
        raise HTTPException(status_code=404, detail="Invitado no encontrado")
    invitado_service.eliminar(invitado_id)
