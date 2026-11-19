from fastapi.testclient import TestClient


def test_login_exitoso(client: TestClient, admin_token: str) -> None:
    assert admin_token


def test_login_credenciales_invalidas(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@nightlife.io", "password": "incorrecta"},
    )
    assert response.status_code == 401


def test_solo_admin_puede_crear_usuarios(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/v1/usuarios",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "nombre": "Promotor Uno",
            "email": "promotor1@nightlife.io",
            "password": "Promo1234",
            "rol": "Promotor",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["rol"] == "Promotor"
    assert "password" not in body


def test_creacion_de_usuario_sin_token_es_rechazada(client: TestClient) -> None:
    response = client.post(
        "/api/v1/usuarios",
        json={
            "nombre": "Promotor Uno",
            "email": "promotor1@nightlife.io",
            "password": "Promo1234",
            "rol": "Promotor",
        },
    )
    assert response.status_code == 401
