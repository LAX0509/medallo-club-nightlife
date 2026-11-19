from datetime import date

from app.core.exceptions import NotFoundError
from app.domain.entities.evento import Evento
from app.domain.enums import EstadoEvento
from app.domain.repositories.evento_repository import EventoRepository


class EventoService:
    def __init__(self, evento_repository: EventoRepository) -> None:
        self._eventos = evento_repository

    def crear(
        self, *, administrador_id: int, nombre: str, fecha: date, aforo_maximo: int,
        tematica: str | None = None
    ) -> Evento:
        evento = Evento(
            id=None,
            administrador_id=administrador_id,
            nombre=nombre,
            fecha=fecha,
            aforo_maximo=aforo_maximo,
            tematica=tematica,
        )
        return self._eventos.crear(evento)

    def obtener(self, evento_id: int) -> Evento:
        evento = self._eventos.obtener_por_id(evento_id)
        if evento is None:
            raise NotFoundError(f"Evento {evento_id} no encontrado")
        return evento

    def listar(self, *, page: int = 1, limit: int = 20) -> tuple[list[Evento], int]:
        return self._eventos.listar(page=page, limit=limit)

    def actualizar(
        self,
        evento_id: int,
        *,
        nombre: str | None,
        fecha: date | None,
        aforo_maximo: int | None,
        tematica: str | None,
        limpiar_tematica: bool,
        estado: EstadoEvento | None,
    ) -> Evento:
        evento = self.obtener(evento_id)
        if nombre is not None:
            evento.nombre = nombre
        if fecha is not None:
            evento.fecha = fecha
        if aforo_maximo is not None:
            evento.aforo_maximo = aforo_maximo
        if tematica is not None:
            evento.tematica = tematica
        elif limpiar_tematica:
            evento.tematica = None
        if estado is not None:
            evento.estado = estado
        return self._eventos.actualizar(evento)

    def eliminar(self, evento_id: int) -> None:
        self.obtener(evento_id)
        self._eventos.eliminar(evento_id)
