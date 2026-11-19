from abc import ABC, abstractmethod

from app.domain.entities.comision import Comision
from app.domain.enums import EstadoComision


class ComisionRepository(ABC):
    @abstractmethod
    def crear(self, comision: Comision) -> Comision: ...

    @abstractmethod
    def obtener_por_id(self, comision_id: int) -> Comision | None: ...

    @abstractmethod
    def listar(
        self,
        *,
        promotor_id: int | None = None,
        evento_id: int | None = None,
        estado: EstadoComision | None = None,
    ) -> list[Comision]: ...

    @abstractmethod
    def actualizar(self, comision: Comision) -> Comision: ...

    @abstractmethod
    def listar_montos_historicos(self, promotor_id: int) -> list[float]: ...
