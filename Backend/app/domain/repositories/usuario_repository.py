from abc import ABC, abstractmethod

from app.domain.entities.usuario import Usuario
from app.domain.enums import RolUsuario


class UsuarioRepository(ABC):
    @abstractmethod
    def crear(self, usuario: Usuario) -> Usuario: ...

    @abstractmethod
    def obtener_por_id(self, usuario_id: int) -> Usuario | None: ...

    @abstractmethod
    def obtener_por_email(self, email: str) -> Usuario | None: ...

    @abstractmethod
    def listar(
        self, *, page: int = 1, limit: int = 20, rol: RolUsuario | None = None
    ) -> tuple[list[Usuario], int]: ...

    @abstractmethod
    def actualizar(self, usuario: Usuario) -> Usuario: ...
