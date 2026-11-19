from fastapi.testclient import TestClient


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _crear_promotor(client: TestClient, admin_token: str, email: str) -> int:
    response = client.post(
        "/api/v1/usuarios",
        headers=_headers(admin_token),
        json={
            "nombre": email.split("@")[0],
            "email": email,
            "password": "Clave1234",
            "rol": "Promotor",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _crear_evento(client: TestClient, admin_token: str) -> int:
    response = client.post(
        "/api/v1/eventos",
        headers=_headers(admin_token),
        json={"nombre": "Evento comisiones", "fecha": "2026-10-10", "aforo_maximo": 100},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_crear_y_liquidar_comision(client: TestClient, admin_token: str) -> None:
    promotor_id = _crear_promotor(client, admin_token, "promotor.com@nightlife.io")
    evento_id = _crear_evento(client, admin_token)

    creada = client.post(
        "/api/v1/comisiones",
        headers=_headers(admin_token),
        json={"promotor_id": promotor_id, "evento_id": evento_id, "porcentaje": "10.00"},
    )
    assert creada.status_code == 201
    comision_id = creada.json()["id"]
    assert creada.json()["estado"] == "pendiente"

    liquidada = client.put(
        f"/api/v1/comisiones/{comision_id}",
        headers=_headers(admin_token),
        json={"estado": "liquidada", "monto": "50000.00"},
    )
    assert liquidada.status_code == 200
    assert liquidada.json()["estado"] == "liquidada"
    assert liquidada.json()["fecha_liquidacion"] is not None


def test_porcentaje_fuera_de_rango_es_rechazado(client: TestClient, admin_token: str) -> None:
    promotor_id = _crear_promotor(client, admin_token, "promotor.rango@nightlife.io")
    evento_id = _crear_evento(client, admin_token)

    response = client.post(
        "/api/v1/comisiones",
        headers=_headers(admin_token),
        json={"promotor_id": promotor_id, "evento_id": evento_id, "porcentaje": "150"},
    )
    assert response.status_code == 422
