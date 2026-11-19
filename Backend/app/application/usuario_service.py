from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import hash_password
from app.domain.entities.usuario import Usuario
from app.domain.enums import RolUsuario
from app.domain.repositories.usuario_repository import UsuarioRepository


class UsuarioService:
    def __init__(self, usuario_repository: UsuarioRepository) -> None:
        self._usuarios = usuario_repository

    def registrar(
        self,
        *,
        nombre: str,
        email: str,
        password: str,
        rol: RolUsuario,
        telefono: str | None,
    ) -> Usuario:
        if self._usuarios.obtener_por_email(email) is not None:
            raise ConflictError(f"Ya existe un usuario registrado con el correo {email}")

        usuario = Usuario(
            id=None,
            nombre=nombre,
            email=email,
            password_hash=hash_password(password),
            rol=rol,
            telefono=telefono,
            estado=True,
        )
        return self._usuarios.crear(usuario)

    def obtener(self, usuario_id: int) -> Usuario:
        usuario = self._usuarios.obtener_por_id(usuario_id)
        if usuario is None:
            raise NotFoundError(f"Usuario {usuario_id} no encontrado")
        return usuario

    def listar(
        self, *, page: int = 1, limit: int = 20, rol: RolUsuario | None = None
    ) -> tuple[list[Usuario], int]:
        return self._usuarios.listar(page=page, limit=limit, rol=rol)

    def actualizar(
        self,
        usuario_id: int,
        *,
        nombre: str | None,
        rol: RolUsuario | None,
        estado: bool | None,
        telefono: str | None,
    ) -> Usuario:
        usuario = self.obtener(usuario_id)
        if nombre is not None:
            usuario.nombre = nombre
        if rol is not None:
            usuario.rol = rol
        if estado is not None:
            usuario.estado = estado
        if telefono is not None:
            usuario.telefono = telefono
        return self._usuarios.actualizar(usuario)

    def validar_rol(self, usuario_id: int, rol_esperado: RolUsuario) -> Usuario:
        usuario = self.obtener(usuario_id)
        if usuario.rol != rol_esperado:
            raise ValidationError(
                f"El usuario {usuario_id} debe tener rol {rol_esperado.value}"
            )
        return usuario
