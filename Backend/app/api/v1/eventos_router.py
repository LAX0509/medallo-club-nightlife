import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_evento_service, require_roles
from app.api.v1.deps import get_db
from app.application import flyer_service
from app.application.evento_service import EventoService
from app.domain.entities.usuario import Usuario
from app.domain.enums import RolUsuario
from app.infrastructure.models.evento_flyer_model import EventoFlyerModel
from app.infrastructure.models.evento_model import EventoModel
from app.schemas.evento_schema import (
    EventoActualizar,
    EventoCrear,
    EventoListaRespuesta,
    EventoRespuesta,
)

router = APIRouter(prefix="/eventos", tags=["Eventos y aforo"])


@router.post(
    "",
    response_model=EventoRespuesta,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def crear_evento(
    payload: EventoCrear,
    usuario: Usuario = Depends(get_current_user),
    evento_service: EventoService = Depends(get_evento_service),
) -> EventoRespuesta:
    evento = evento_service.crear(
        administrador_id=usuario.id,
        nombre=payload.nombre,
        fecha=payload.fecha,
        aforo_maximo=payload.aforo_maximo,
        tematica=payload.tematica,
    )
    return EventoRespuesta.model_validate(evento)


@router.get("", response_model=EventoListaRespuesta, dependencies=[Depends(get_current_user)])
def listar_eventos(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    evento_service: EventoService = Depends(get_evento_service),
) -> EventoListaRespuesta:
    eventos, total = evento_service.listar(page=page, limit=limit)
    return EventoListaRespuesta(
        items=[EventoRespuesta.model_validate(e) for e in eventos],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{evento_id}", response_model=EventoRespuesta, dependencies=[Depends(get_current_user)]
)
def obtener_evento(
    evento_id: int, evento_service: EventoService = Depends(get_evento_service)
) -> EventoRespuesta:
    return EventoRespuesta.model_validate(evento_service.obtener(evento_id))


@router.put(
    "/{evento_id}",
    response_model=EventoRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def actualizar_evento(
    evento_id: int,
    payload: EventoActualizar,
    evento_service: EventoService = Depends(get_evento_service),
) -> EventoRespuesta:
    evento = evento_service.actualizar(
        evento_id,
        nombre=payload.nombre,
        fecha=payload.fecha,
        aforo_maximo=payload.aforo_maximo,
        tematica=payload.tematica,
        limpiar_tematica="tematica" in payload.model_fields_set and payload.tematica is None,
        estado=payload.estado,
    )
    return EventoRespuesta.model_validate(evento)


def _evento_o_404(db: Session, evento_id: int) -> EventoModel:
    evento = db.get(EventoModel, evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    return evento


@router.post(
    "/{evento_id}/flyer",
    response_model=EventoRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
async def cargar_flyer_evento(
    evento_id: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> EventoRespuesta:
    """Sube un flyer pequeño en una sola solicitud (los grandes usan /flyer/partes)."""
    evento = _evento_o_404(db, evento_id)
    tipo = archivo.content_type or ""
    if tipo not in flyer_service.FLYER_TYPES:
        raise HTTPException(status_code=415, detail="Usa una imagen JPG, PNG, WEBP o GIF, o un video MP4/WEBM.")
    contenido = await archivo.read(flyer_service.MAX_PARTE_BYTES + 1)
    try:
        flyer_service.guardar_completo(db, evento, tipo, contenido)
    except flyer_service.FlyerError as exc:
        raise HTTPException(status_code=exc.codigo, detail=exc.detalle) from exc
    db.refresh(evento)
    return EventoRespuesta.model_validate(evento)


@router.post(
    "/{evento_id}/flyer/partes",
    response_model=EventoRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
async def cargar_parte_flyer_evento(
    evento_id: int,
    subida: str = Form(...),
    orden: int = Form(...),
    total: int = Form(...),
    tipo: str = Form(...),
    tamano_total: int = Form(...),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> EventoRespuesta:
    """Recibe un trozo del flyer; cuando llegan todos, el flyer queda publicado."""
    evento = _evento_o_404(db, evento_id)
    datos = await archivo.read(flyer_service.MAX_PARTE_BYTES + 1)
    try:
        flyer_service.recibir_parte(
            db, evento, subida=subida, orden=orden, total=total, tipo=tipo, tamano_total=tamano_total, datos=datos
        )
    except flyer_service.FlyerError as exc:
        raise HTTPException(status_code=exc.codigo, detail=exc.detalle) from exc
    db.refresh(evento)
    return EventoRespuesta.model_validate(evento)


@router.get("/{evento_id}/flyer/{nombre}", include_in_schema=False)
def ver_flyer_evento(evento_id: int, nombre: str, request: Request, db: Session = Depends(get_db)) -> Response:
    """Entrega el flyer (público); admite ``Range`` para que los videos se reproduzcan por trozos."""
    inicio = fin = None
    pedido_por_rango = False
    rango = request.headers.get("range", "")
    coincide = re.fullmatch(r"bytes=(\d*)-(\d*)", rango.strip())
    if coincide and (coincide.group(1) or coincide.group(2)):
        pedido_por_rango = True
        if coincide.group(1):
            inicio = int(coincide.group(1))
            fin = int(coincide.group(2)) if coincide.group(2) else None
        else:  # últimos N bytes
            ultimos = int(coincide.group(2))
            meta = db.get(EventoFlyerModel, evento_id)
            if meta is not None:
                inicio, fin = max(meta.tamano - ultimos, 0), None
    resultado = flyer_service.leer_rango(db, evento_id, inicio, fin)
    if resultado is None:
        raise HTTPException(status_code=404, detail="Este evento no tiene flyer.")
    contenido, ini, fin_real, total, tipo = resultado
    cabeceras = {"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=31536000, immutable"}
    if ini >= total:
        cabeceras["Content-Range"] = f"bytes */{total}"
        return Response(status_code=416, headers=cabeceras)
    parcial = pedido_por_rango or (fin_real - ini + 1) < total
    if parcial:
        cabeceras["Content-Range"] = f"bytes {ini}-{fin_real}/{total}"
    return Response(content=contenido, status_code=206 if parcial else 200, media_type=tipo, headers=cabeceras)


@router.delete(
    "/{evento_id}/flyer",
    response_model=EventoRespuesta,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def eliminar_flyer_evento(evento_id: int, db: Session = Depends(get_db)) -> EventoRespuesta:
    evento = _evento_o_404(db, evento_id)
    flyer_service.quitar(db, evento)
    db.refresh(evento)
    return EventoRespuesta.model_validate(evento)


@router.delete(
    "/{evento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def eliminar_evento(
    evento_id: int,
    evento_service: EventoService = Depends(get_evento_service),
    db: Session = Depends(get_db),
) -> None:
    evento = db.get(EventoModel, evento_id)
    if evento is not None:
        flyer_service.quitar(db, evento, confirmar=False)
        db.flush()
    try:
        evento_service.eliminar(evento_id)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar esta fecha porque ya tiene reservas, invitados, accesos o movimientos. "
            "Puedes cerrarla cambiando su estado a «Cerrado».",
        ) from exc
