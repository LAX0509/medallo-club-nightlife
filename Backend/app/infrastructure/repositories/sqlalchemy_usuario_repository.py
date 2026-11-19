from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.entities.usuario import Usuario
from app.domain.enums import RolUsuario
from app.domain.repositories.usuario_repository import UsuarioRepository
from app.infrastructure.models.usuario_model import UsuarioModel


def _to_entity(model: UsuarioModel) -> Usuario:
    return Usuario(
        id=model.id,
        nombre=model.nombre,
        email=model.email,
        password_hash=model.password_hash,
        rol=RolUsuario(model.rol),
        telefono=model.telefono,
        estado=model.estado,
        fecha_registro=model.fecha_registro,
    )


class SqlAlchemyUsuarioRepository(UsuarioRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def crear(self, usuario: Usuario) -> Usuario:
        model = UsuarioModel(
            nombre=usuario.nombre,
            email=usuario.email,
            password_hash=usuario.password_hash,
            rol=usuario.rol.value,
            telefono=usuario.telefono,
            estado=usuario.estado,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)

    def obtener_por_id(self, usuario_id: int) -> Usuario | None:
        model = self._session.get(UsuarioModel, usuario_id)
        return _to_entity(model) if model else None

    def obtener_por_email(self, email: str) -> Usuario | None:
        stmt = select(UsuarioModel).where(UsuarioModel.email == email)
        model = self._session.execute(stmt).scalar_one_or_none()
        return _to_entity(model) if model else None

    def listar(
        self, *, page: int = 1, limit: int = 20, rol: RolUsuario | None = None
    ) -> tuple[list[Usuario], int]:
        stmt = select(UsuarioModel)
        count_stmt = select(func.count()).select_from(UsuarioModel)
        if rol is not None:
            stmt = stmt.where(UsuarioModel.rol == rol.value)
            count_stmt = count_stmt.where(UsuarioModel.rol == rol.value)
        total = self._session.execute(count_stmt).scalar_one()
        stmt = stmt.order_by(UsuarioModel.id).offset((page - 1) * limit).limit(limit)
        models = self._session.execute(stmt).scalars().all()
        return [_to_entity(m) for m in models], total

    def actualizar(self, usuario: Usuario) -> Usuario:
        model = self._session.get(UsuarioModel, usuario.id)
        if model is None:
            raise ValueError(f"Usuario {usuario.id} no encontrado")
        model.nombre = usuario.nombre
        model.rol = usuario.rol.value
        model.telefono = usuario.telefono
        model.estado = usuario.estado
        model.password_hash = usuario.password_hash
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)
