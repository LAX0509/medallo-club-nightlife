from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.entities.evento import Evento
from app.domain.enums import EstadoEvento
from app.domain.repositories.evento_repository import EventoRepository
from app.infrastructure.models.evento_model import EventoModel


def _to_entity(model: EventoModel) -> Evento:
    return Evento(
        id=model.id,
        administrador_id=model.administrador_id,
        nombre=model.nombre,
        fecha=model.fecha,
        aforo_maximo=model.aforo_maximo,
        tematica=model.tematica,
        flyer_url=model.flyer_url,
        estado=EstadoEvento(model.estado),
    )


class SqlAlchemyEventoRepository(EventoRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def crear(self, evento: Evento) -> Evento:
        model = EventoModel(
            administrador_id=evento.administrador_id,
            nombre=evento.nombre,
            fecha=evento.fecha,
            aforo_maximo=evento.aforo_maximo,
            tematica=evento.tematica,
            flyer_url=evento.flyer_url,
            estado=evento.estado.value,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)

    def obtener_por_id(self, evento_id: int) -> Evento | None:
        model = self._session.get(EventoModel, evento_id)
        return _to_entity(model) if model else None

    def listar(self, *, page: int = 1, limit: int = 20) -> tuple[list[Evento], int]:
        total = self._session.execute(
            select(func.count()).select_from(EventoModel)
        ).scalar_one()
        stmt = (
            select(EventoModel)
            .order_by(EventoModel.fecha.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        models = self._session.execute(stmt).scalars().all()
        return [_to_entity(m) for m in models], total

    def actualizar(self, evento: Evento) -> Evento:
        model = self._session.get(EventoModel, evento.id)
        if model is None:
            raise ValueError(f"Evento {evento.id} no encontrado")
        model.nombre = evento.nombre
        model.fecha = evento.fecha
        model.aforo_maximo = evento.aforo_maximo
        model.tematica = evento.tematica
        model.flyer_url = evento.flyer_url
        model.estado = evento.estado.value
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)

    def eliminar(self, evento_id: int) -> None:
        model = self._session.get(EventoModel, evento_id)
        if model is not None:
            self._session.delete(model)
            self._session.commit()
