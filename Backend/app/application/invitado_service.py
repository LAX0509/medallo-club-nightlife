import secrets

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.invitado import Invitado
from app.domain.repositories.evento_repository import EventoRepository
from app.domain.repositories.invitado_repository import InvitadoRepository
from app.domain.repositories.usuario_repository import UsuarioRepository
from app.domain.enums import RolUsuario


def generar_qr_code(evento_id: int) -> str:
    """Genera un identificador único e impredecible para el pase de un invitado."""
    return f"NLD-{evento_id}-{secrets.token_urlsafe(16)}"


class InvitadoService:
    def __init__(
        self,
        invitado_repository: InvitadoRepository,
        evento_repository: EventoRepository,
        usuario_repository: UsuarioRepository,
    ) -> None:
        self._invitados = invitado_repository
        self._eventos = evento_repository
        self._usuarios = usuario_repository

    def registrar(self, *, nombre: str, evento_id: int, promotor_id: int) -> Invitado:
        evento = self._eventos.obtener_por_id(evento_id)
        if evento is None:
            raise NotFoundError(f"Evento {evento_id} no encontrado")

        promotor = self._usuarios.obtener_por_id(promotor_id)
        if promotor is None:
            raise NotFoundError(f"Promotor {promotor_id} no encontrado")
        if promotor.rol != RolUsuario.PROMOTOR:
            raise ValidationError(
                f"El usuario {promotor_id} no tiene rol Promotor"
            )

        qr_code = generar_qr_code(evento_id)
        invitado = Invitado(
            id=None, evento_id=evento_id, promotor_id=promotor_id, nombre=nombre, qr_code=qr_code
        )
        return self._invitados.crear(invitado)

    def obtener(self, invitado_id: int) -> Invitado:
        invitado = self._invitados.obtener_por_id(invitado_id)
        if invitado is None:
            raise NotFoundError(f"Invitado {invitado_id} no encontrado")
        return invitado

    def listar(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        evento_id: int | None = None,
        promotor_id: int | None = None,
    ) -> tuple[list[Invitado], int]:
        return self._invitados.listar(
            page=page, limit=limit, evento_id=evento_id, promotor_id=promotor_id
        )

    def eliminar(self, invitado_id: int) -> None:
        self.obtener(invitado_id)
        self._invitados.eliminar(invitado_id)
