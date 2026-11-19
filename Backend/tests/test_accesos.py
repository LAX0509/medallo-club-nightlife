from fastapi.testclient import TestClient


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _crear_usuario(client: TestClient, admin_token: str, *, email: str, rol: str) -> int:
    response = client.post(
        "/api/v1/usuarios",
        headers=_headers(admin_token),
        json={"nombre": email.split("@")[0], "email": email, "password": "Clave1234", "rol": rol},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _login(client: TestClient, email: str, password: str = "Clave1234") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _crear_evento(client: TestClient, admin_token: str, *, aforo_maximo: int) -> int:
    response = client.post(
        "/api/v1/eventos",
        headers=_headers(admin_token),
        json={"nombre": "Noche de prueba", "fecha": "2026-10-10", "aforo_maximo": aforo_maximo},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_flujo_completo_de_acceso_qr(client: TestClient, admin_token: str) -> None:
    promotor_id = _crear_usuario(
        client, admin_token, email="promotor@nightlife.io", rol="Promotor"
    )
    puerta_id = _crear_usuario(client, admin_token, email="puerta@nightlife.io", rol="Puerta")
    puerta_token = _login(client, "puerta@nightlife.io")
    evento_id = _crear_evento(client, admin_token, aforo_maximo=1)

    invitado_resp = client.post(
        "/api/v1/invitados",
        headers=_headers(admin_token),
        json={"nombre": "Invitado Uno", "evento_id": evento_id, "promotor_id": promotor_id},
    )
    assert invitado_resp.status_code == 201
    qr_code = invitado_resp.json()["qr_code"]

    # Primer escaneo: válido.
    primer = client.post(
        "/api/v1/accesos",
        headers=_headers(puerta_token),
        json={"evento_id": evento_id, "qr_code": qr_code, "tipo": "qr"},
    )
    assert primer.status_code == 201
    assert primer.json()["acceso"]["resultado"] == "valido"

    # Reintento con el mismo QR: duplicado + alerta de riesgo alto.
    segundo = client.post(
        "/api/v1/accesos",
        headers=_headers(puerta_token),
        json={"evento_id": evento_id, "qr_code": qr_code, "tipo": "qr"},
    )
    assert segundo.status_code == 201
    body = segundo.json()
    assert body["acceso"]["resultado"] == "duplicado"
    assert any(a["tipo_alerta"] == "cortesia_duplicada" for a in body["alertas_generadas"])


def test_cortesia_manual_requiere_justificacion(client: TestClient, admin_token: str) -> None:
    evento_id = _crear_evento(client, admin_token, aforo_maximo=10)
    response = client.post(
        "/api/v1/accesos",
        headers=_headers(admin_token),
        json={"evento_id": evento_id, "tipo": "cortesia_manual"},
    )
    assert response.status_code == 422


def test_sobreaforo_rechaza_nuevos_ingresos(client: TestClient, admin_token: str) -> None:
    promotor_id = _crear_usuario(
        client, admin_token, email="promotor2@nightlife.io", rol="Promotor"
    )
    evento_id = _crear_evento(client, admin_token, aforo_maximo=1)

    primer_invitado = client.post(
        "/api/v1/invitados",
        headers=_headers(admin_token),
        json={"nombre": "Invitado A", "evento_id": evento_id, "promotor_id": promotor_id},
    ).json()
    segundo_invitado = client.post(
        "/api/v1/invitados",
        headers=_headers(admin_token),
        json={"nombre": "Invitado B", "evento_id": evento_id, "promotor_id": promotor_id},
    ).json()

    ok = client.post(
        "/api/v1/accesos",
        headers=_headers(admin_token),
        json={
            "evento_id": evento_id,
            "qr_code": primer_invitado["qr_code"],
            "tipo": "qr",
        },
    )
    assert ok.json()["acceso"]["resultado"] == "valido"

    rechazado = client.post(
        "/api/v1/accesos",
        headers=_headers(admin_token),
        json={
            "evento_id": evento_id,
            "qr_code": segundo_invitado["qr_code"],
            "tipo": "qr",
        },
    )
    assert rechazado.json()["acceso"]["resultado"] == "rechazado"


def test_dos_lectores_simultaneos_del_mismo_qr_solo_dejan_pasar_a_uno(
    client: TestClient, admin_token: str, db_session, monkeypatch
) -> None:
    """Regresión de concurrencia: si dos puertas leen el pase como 'pendiente' a la vez,
    el cambio pendiente -> usado es atómico y solo una obtiene el ingreso válido."""
    from app.application.acceso_service import AccesoService
    from app.application.risk_engine import RiskEngine
    from app.core.config import Settings
    from app.infrastructure.repositories import (
        SqlAlchemyAccesoQRRepository,
        SqlAlchemyAlertaRiesgoRepository,
        SqlAlchemyEventoRepository,
        SqlAlchemyInvitadoRepository,
    )

    promotor_id = _crear_usuario(client, admin_token, email="promo.race@nightlife.io", rol="Promotor")
    evento_id = _crear_evento(client, admin_token, aforo_maximo=50)
    invitado = client.post(
        "/api/v1/invitados",
        headers=_headers(admin_token),
        json={"nombre": "Carrera", "evento_id": evento_id, "promotor_id": promotor_id},
    ).json()

    invitados = SqlAlchemyInvitadoRepository(db_session)
    servicio = AccesoService(
        SqlAlchemyAccesoQRRepository(db_session),
        invitados,
        SqlAlchemyEventoRepository(db_session),
        SqlAlchemyAlertaRiesgoRepository(db_session),
        RiskEngine(Settings()),
    )
    lectura_vieja = invitados.obtener_por_qr(invitado["qr_code"])  # la puerta B leyó antes de que A termine

    primero = servicio.registrar_acceso_qr(evento_id=evento_id, qr_code=invitado["qr_code"])
    assert primero.acceso.resultado.value == "valido"

    monkeypatch.setattr(invitados, "obtener_por_qr", lambda _qr: lectura_vieja)  # B sigue viendo 'pendiente'
    segundo = servicio.registrar_acceso_qr(evento_id=evento_id, qr_code=invitado["qr_code"])
    assert segundo.acceso.resultado.value == "duplicado"
    assert any(a.tipo_alerta.value == "cortesia_duplicada" for a in segundo.alertas_generadas)
    assert servicio._aforo_actual(evento_id) == 1  # un solo ingreso contado


def test_marcar_usado_si_pendiente_es_atomico(db_session, client: TestClient, admin_token: str) -> None:
    from app.infrastructure.repositories import SqlAlchemyInvitadoRepository

    promotor_id = _crear_usuario(client, admin_token, email="promo.cas@nightlife.io", rol="Promotor")
    evento_id = _crear_evento(client, admin_token, aforo_maximo=5)
    invitado = client.post(
        "/api/v1/invitados",
        headers=_headers(admin_token),
        json={"nombre": "CAS", "evento_id": evento_id, "promotor_id": promotor_id},
    ).json()
    repo = SqlAlchemyInvitadoRepository(db_session)
    assert repo.marcar_usado_si_pendiente(invitado["id"]) is True
    assert repo.marcar_usado_si_pendiente(invitado["id"]) is False
