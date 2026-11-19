from abc import ABC, abstractmethod
from contextlib import AbstractContextManager

from app.domain.entities.acceso_qr import AccesoQR
from app.domain.enums import ResultadoAcceso


class AccesoQRRepository(ABC):
    @abstractmethod
    def crear(self, acceso: AccesoQR) -> AccesoQR: ...

    @abstractmethod
    def obtener_por_id(self, acceso_id: int) -> AccesoQR | None: ...

    @abstractmethod
    def listar(
        self, *, page: int = 1, limit: int = 20, evento_id: int | None = None
    ) -> tuple[list[AccesoQR], int]: ...

    @abstractmethod
    def actualizar(self, acceso: AccesoQR) -> AccesoQR: ...

    @abstractmethod
    def eliminar(self, acceso_id: int) -> None: ...

    @abstractmethod
    def bloquear_evento(self, evento_id: int) -> AbstractContextManager[None]:
        """Serializa los registros de acceso de un evento (varias puertas a la vez)."""

    @abstractmethod
    def contar_por_evento_y_resultado(
        self, evento_id: int, resultado: ResultadoAcceso
    ) -> int: ...
