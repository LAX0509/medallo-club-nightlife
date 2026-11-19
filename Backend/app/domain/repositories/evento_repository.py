from abc import ABC, abstractmethod

from app.domain.entities.evento import Evento


class EventoRepository(ABC):
    @abstractmethod
    def crear(self, evento: Evento) -> Evento: ...

    @abstractmethod
    def obtener_por_id(self, evento_id: int) -> Evento | None: ...

    @abstractmethod
    def listar(self, *, page: int = 1, limit: int = 20) -> tuple[list[Evento], int]: ...

    @abstractmethod
    def actualizar(self, evento: Evento) -> Evento: ...

    @abstractmethod
    def eliminar(self, evento_id: int) -> None: ...
