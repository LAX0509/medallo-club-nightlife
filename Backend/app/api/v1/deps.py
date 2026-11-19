from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.application.acceso_service import AccesoService
from app.application.alerta_service import AlertaService
from app.application.auth_service import AuthService
from app.application.comision_service import ComisionService
from app.application.dashboard_service import DashboardService
from app.application.evento_service import EventoService
from app.application.invitado_service import InvitadoService
from app.application.risk_engine import RiskEngine
from app.application.usuario_service import UsuarioService
from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.domain.entities.usuario import Usuario
from app.domain.enums import RolUsuario
from app.infrastructure.database.session import get_db
from app.infrastructure.repositories import (
    SqlAlchemyAccesoQRRepository,
    SqlAlchemyAlertaRiesgoRepository,
    SqlAlchemyComisionRepository,
    SqlAlchemyEventoRepository,
    SqlAlchemyInvitadoRepository,
    SqlAlchemyUsuarioRepository,
)

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


def get_usuario_repository(db: Session = Depends(get_db)) -> SqlAlchemyUsuarioRepository:
    return SqlAlchemyUsuarioRepository(db)


def get_evento_repository(db: Session = Depends(get_db)) -> SqlAlchemyEventoRepository:
    return SqlAlchemyEventoRepository(db)


def get_invitado_repository(db: Session = Depends(get_db)) -> SqlAlchemyInvitadoRepository:
    return SqlAlchemyInvitadoRepository(db)


def get_comision_repository(db: Session = Depends(get_db)) -> SqlAlchemyComisionRepository:
    return SqlAlchemyComisionRepository(db)


def get_acceso_repository(db: Session = Depends(get_db)) -> SqlAlchemyAccesoQRRepository:
    return SqlAlchemyAccesoQRRepository(db)


def get_alerta_repository(db: Session = Depends(get_db)) -> SqlAlchemyAlertaRiesgoRepository:
    return SqlAlchemyAlertaRiesgoRepository(db)


def get_risk_engine(settings: Settings = Depends(get_settings)) -> RiskEngine:
    return RiskEngine(settings)


def get_auth_service(
    usuario_repository: SqlAlchemyUsuarioRepository = Depends(get_usuario_repository),
) -> AuthService:
    return AuthService(usuario_repository)


def get_usuario_service(
    usuario_repository: SqlAlchemyUsuarioRepository = Depends(get_usuario_repository),
) -> UsuarioService:
    return UsuarioService(usuario_repository)


def get_evento_service(
    evento_repository: SqlAlchemyEventoRepository = Depends(get_evento_repository),
) -> EventoService:
    return EventoService(evento_repository)


def get_invitado_service(
    invitado_repository: SqlAlchemyInvitadoRepository = Depends(get_invitado_repository),
    evento_repository: SqlAlchemyEventoRepository = Depends(get_evento_repository),
    usuario_repository: SqlAlchemyUsuarioRepository = Depends(get_usuario_repository),
) -> InvitadoService:
    return InvitadoService(invitado_repository, evento_repository, usuario_repository)


def get_comision_service(
    comision_repository: SqlAlchemyComisionRepository = Depends(get_comision_repository),
    invitado_repository: SqlAlchemyInvitadoRepository = Depends(get_invitado_repository),
    evento_repository: SqlAlchemyEventoRepository = Depends(get_evento_repository),
    usuario_repository: SqlAlchemyUsuarioRepository = Depends(get_usuario_repository),
    alerta_repository: SqlAlchemyAlertaRiesgoRepository = Depends(get_alerta_repository),
    risk_engine: RiskEngine = Depends(get_risk_engine),
    settings: Settings = Depends(get_settings),
) -> ComisionService:
    return ComisionService(
        comision_repository,
        invitado_repository,
        evento_repository,
        usuario_repository,
        alerta_repository,
        risk_engine,
        settings,
    )


def get_acceso_service(
    acceso_repository: SqlAlchemyAccesoQRRepository = Depends(get_acceso_repository),
    invitado_repository: SqlAlchemyInvitadoRepository = Depends(get_invitado_repository),
    evento_repository: SqlAlchemyEventoRepository = Depends(get_evento_repository),
    alerta_repository: SqlAlchemyAlertaRiesgoRepository = Depends(get_alerta_repository),
    risk_engine: RiskEngine = Depends(get_risk_engine),
) -> AccesoService:
    return AccesoService(
        acceso_repository, invitado_repository, evento_repository, alerta_repository, risk_engine
    )


def get_alerta_service(
    alerta_repository: SqlAlchemyAlertaRiesgoRepository = Depends(get_alerta_repository),
) -> AlertaService:
    return AlertaService(alerta_repository)


def get_dashboard_service(
    evento_repository: SqlAlchemyEventoRepository = Depends(get_evento_repository),
    acceso_repository: SqlAlchemyAccesoQRRepository = Depends(get_acceso_repository),
    comision_repository: SqlAlchemyComisionRepository = Depends(get_comision_repository),
    alerta_repository: SqlAlchemyAlertaRiesgoRepository = Depends(get_alerta_repository),
) -> DashboardService:
    return DashboardService(
        evento_repository, acceso_repository, comision_repository, alerta_repository
    )


def get_current_user(
    token: str | None = Depends(_oauth2_scheme),
    usuario_repository: SqlAlchemyUsuarioRepository = Depends(get_usuario_repository),
) -> Usuario:
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credenciales_invalidas
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise credenciales_invalidas from exc

    usuario_id = payload.get("sub")
    if usuario_id is None:
        raise credenciales_invalidas

    usuario = usuario_repository.obtener_por_id(int(usuario_id))
    if usuario is None or not usuario.esta_activo:
        raise credenciales_invalidas
    return usuario


def require_roles(*roles: RolUsuario) -> Callable[[Usuario], Usuario]:
    def _verificar(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"El rol {usuario.rol.value} no tiene permisos para esta acción",
            )
        return usuario

    return _verificar
