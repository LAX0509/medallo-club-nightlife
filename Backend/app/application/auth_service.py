from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, verify_password
from app.domain.entities.usuario import Usuario
from app.domain.repositories.usuario_repository import UsuarioRepository


class AuthService:
    def __init__(self, usuario_repository: UsuarioRepository) -> None:
        self._usuarios = usuario_repository

    def autenticar(self, email: str, password: str) -> tuple[Usuario, str]:
        usuario = self._usuarios.obtener_por_email(email)
        if usuario is None or not verify_password(password, usuario.password_hash):
            raise AuthenticationError("Credenciales inválidas")
        if not usuario.esta_activo:
            raise AuthenticationError("El usuario se encuentra inactivo")

        token = create_access_token(
            subject=str(usuario.id),
            extra_claims={"rol": usuario.rol.value, "nombre": usuario.nombre},
        )
        return usuario, token
