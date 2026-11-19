from abc import ABC, abstractmethod

from app.domain.entities.invitado import Invitado


class InvitadoRepository(ABC):
    @abstractmethod
    def crear(self, invitado: Invitado) -> Invitado: ...

    @abstractmethod
    def obtener_por_id(self, invitado_id: int) -> Invitado | None: ...

    @abstractmethod
    def obtener_por_qr(self, qr_code: str) -> Invitado | None: ...

    @abstractmethod
    def listar(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        evento_id: int | None = None,
        promotor_id: int | None = None,
    ) -> tuple[list[Invitado], int]: ...

    @abstractmethod
    def actualizar(self, invitado: Invitado) -> Invitado: ...

    @abstractmethod
    def marcar_usado_si_pendiente(self, invitado_id: int) -> bool:
        """Marca el pase como usado de forma atómica (compare-and-set).

        Devuelve ``True`` solo para quien logra el cambio ``pendiente -> usado``; si otro
        lector se adelantó en el mismo instante devuelve ``False``.
        """

    @abstractmethod
    def eliminar(self, invitado_id: int) -> None: ...

    @abstractmethod
    def contar_por_evento_y_promotor(self, evento_id: int, promotor_id: int) -> int: ...
