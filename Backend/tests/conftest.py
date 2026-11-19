from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.domain.enums import RolUsuario
from app.infrastructure.database.session import Base, get_db
from app.infrastructure.models.usuario_model import UsuarioModel
from app.main import app

_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def _reset_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(autouse=True)
def _aislar_servicios_externos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las pruebas nunca deben hablar con Meta ni con la IA real (el .env puede tener claves)."""
    from app.application import whatsapp_notification_service
    from app.application.ia_client import ClienteIA

    def _http_bloqueado(*args, **kwargs):
        raise AssertionError("HTTP real bloqueado durante las pruebas (WhatsApp).")

    monkeypatch.setattr(whatsapp_notification_service.httpx, "post", _http_bloqueado)
    monkeypatch.setattr(ClienteIA, "configurada", property(lambda self: False))
    # Las pruebas no dependen del .env del equipo: sin destinos ni plantillas de WhatsApp salvo que la prueba los defina.
    from app.core.config import get_settings

    ajustes = get_settings()
    for campo in ("whatsapp_access_token", "whatsapp_phone_number_id", "whatsapp_notify_to", "whatsapp_inventory_notify_to",
                  "whatsapp_inventory_template_name", "whatsapp_confirmation_template_name"):
        monkeypatch.setattr(ajustes, campo, "")


def _override_get_db() -> Generator[Session, None, None]:
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    session = _TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin_token(client: TestClient, db_session: Session) -> str:
    admin = UsuarioModel(
        nombre="Admin Principal",
        email="admin@nightlife.io",
        password_hash=hash_password("Admin1234"),
        rol=RolUsuario.ADMINISTRADOR.value,
        estado=True,
    )
    db_session.add(admin)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login", json={"email": "admin@nightlife.io", "password": "Admin1234"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def crear_evento(client: TestClient, auth: dict[str, str]):
    def _crear(nombre: str = "Noche Test", dias: int = 5, aforo: int = 100, tematica: str | None = None) -> dict:
        from datetime import date, timedelta

        cuerpo = {"nombre": nombre, "fecha": (date.today() + timedelta(days=dias)).isoformat(), "aforo_maximo": aforo}
        if tematica:
            cuerpo["tematica"] = tematica
        respuesta = client.post("/api/v1/eventos", json=cuerpo, headers=auth)
        assert respuesta.status_code == 201, respuesta.text
        return respuesta.json()

    return _crear


@pytest.fixture
def crear_usuario(client: TestClient, auth: dict[str, str]):
    def _crear(email: str, rol: str, password: str = "Clave1234") -> dict:
        respuesta = client.post(
            "/api/v1/usuarios",
            json={"nombre": email.split("@")[0].title(), "email": email, "password": password, "rol": rol},
            headers=auth,
        )
        assert respuesta.status_code == 201, respuesta.text
        token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
        return {**respuesta.json(), "headers": {"Authorization": f"Bearer {token}"}}

    return _crear
