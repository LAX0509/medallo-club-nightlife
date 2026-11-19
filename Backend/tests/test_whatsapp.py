import hashlib
import hmac
import json
from datetime import date, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.reserva_model import ReservaModel
from app.infrastructure.models.usuario_model import UsuarioModel
from app.infrastructure.models.whatsapp_inbound_message_model import WhatsAppInboundMessageModel


def _signed_payload(payload: dict, secret: str) -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body, signature


def test_webhook_responds_once_and_reports_inbound_sentiment(
    client: TestClient,
    db_session: Session,
    admin_token: str,
    monkeypatch,
) -> None:
    secret = "webhook-test-secret"
    settings = SimpleNamespace(
        whatsapp_app_secret=secret,
        whatsapp_webhook_verify_token="verify-me",
        whatsapp_reservation_page_url="https://club.example/reservas",
    )
    monkeypatch.setattr("app.api.v1.whatsapp_router.get_settings", lambda: settings)
    llamadas = []

    def responder(telefono: str, texto: str):
        llamadas.append((telefono, texto))
        return ("respondido", None)

    monkeypatch.setattr(
        "app.api.v1.whatsapp_router.responder_mensaje_bot_whatsapp",
        responder,
    )

    verificacion = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-me",
            "hub.challenge": "challenge-123",
        },
    )
    assert verificacion.status_code == 200
    assert verificacion.text == "challenge-123"

    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "id": "wamid.inbound.1",
                        "from": "573001234567",
                        "type": "text",
                        "text": {"body": "La reserva fue horrible"},
                    }]
                }
            }]
        }],
    }
    body, signature = _signed_payload(payload, secret)
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": signature}

    primera = client.post("/webhooks/whatsapp", content=body, headers=headers)
    segunda = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert len(llamadas) == 1
    assert "Lamentamos" in llamadas[0][1]
    assert "https://club.example/reservas" in llamadas[0][1]

    registro = db_session.get(WhatsAppInboundMessageModel, "wamid.inbound.1")
    assert registro is not None
    assert registro.sentiment == "negativo"
    assert registro.response_status == "respondido"

    resumen = client.get(
        "/api/v1/sentimientos/whatsapp/resumen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resumen.status_code == 200
    assert resumen.json() == {"total": 1, "positivo": 0, "neutral": 0, "negativo": 1}


def test_reservation_confirmation_delivery_is_updated_from_meta_webhook(
    client: TestClient,
    db_session: Session,
    admin_token: str,
    monkeypatch,
) -> None:
    admin = db_session.execute(
        select(UsuarioModel).where(UsuarioModel.email == "admin@nightlife.io")
    ).scalar_one()
    evento = EventoModel(
        administrador_id=admin.id,
        nombre="Noche confirmación",
        fecha=date.today() + timedelta(days=5),
        aforo_maximo=100,
        estado="planeado",
    )
    db_session.add(evento)
    db_session.commit()
    db_session.refresh(evento)

    monkeypatch.setattr("app.api.v1.reservas_router.notificar_nueva_reserva", lambda _datos: None)
    monkeypatch.setattr(
        "app.api.v1.reservas_router.notificar_confirmacion_reserva",
        lambda _datos: ("enviada", None, "wamid.confirm.1"),
    )
    creada = client.post(
        "/api/v1/reservas",
        json={
            "evento_id": evento.id,
            "nombre_cliente": "Alejo Prueba",
            "telefono": "+57 300 123 4567",
            "tipo": "mesa",
            "asistentes": 3,
        },
    )
    assert creada.status_code == 201
    reserva_id = creada.json()["id"]
    token = {"Authorization": f"Bearer {admin_token}"}
    confirmada = client.patch(
        f"/api/v1/reservas/{reserva_id}/estado",
        json={"estado": "confirmada"},
        headers=token,
    )
    assert confirmada.status_code == 200
    assert confirmada.json()["whatsapp_confirmacion_estado"] == "enviada"

    secret = "delivery-webhook-secret"
    monkeypatch.setattr(
        "app.api.v1.whatsapp_router.get_settings",
        lambda: SimpleNamespace(whatsapp_app_secret=secret),
    )
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{"id": "wamid.confirm.1", "status": "delivered"}]
                }
            }]
        }],
    }
    body, signature = _signed_payload(payload, secret)
    respuesta = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
    )
    assert respuesta.status_code == 200

    db_session.refresh(db_session.get(ReservaModel, reserva_id))
    reserva = db_session.get(ReservaModel, reserva_id)
    assert reserva is not None
    assert reserva.whatsapp_confirmacion_estado == "entregada"
    assert reserva.whatsapp_confirmacion_message_id == "wamid.confirm.1"
