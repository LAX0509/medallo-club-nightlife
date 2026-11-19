from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.reserva_model import ReservaModel
from app.infrastructure.models.usuario_model import UsuarioModel


def test_chat_can_list_events_create_and_cancel_reservation(
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
        nombre="Noche de prueba",
        fecha=date.today() + timedelta(days=10),
        aforo_maximo=200,
        estado="planeado",
    )
    db_session.add(evento)
    db_session.commit()
    db_session.refresh(evento)

    # No enviar mensajes reales a WhatsApp durante una prueba local.
    monkeypatch.setattr(
        "app.api.v1.reservas_router.notificar_nueva_reserva",
        lambda _datos: None,
    )

    eventos = client.get("/api/v1/reservas/eventos")
    assert eventos.status_code == 200
    assert any(item["id"] == evento.id for item in eventos.json())

    creada = client.post(
        "/api/v1/reservas",
        json={
            "evento_id": evento.id,
            "nombre_cliente": "Cliente de prueba",
            "telefono": "+57 300 123 4567",
            "tipo": "mesa",
            "asistentes": 4,
            "notas": "Prueba del chat",
        },
    )
    assert creada.status_code == 201
    reserva_json = creada.json()
    assert reserva_json["estado"] == "pendiente"
    assert reserva_json["nombre_cliente"] == "Cliente de prueba"
    assert reserva_json["token_cancelacion"]

    reserva_guardada = db_session.get(ReservaModel, reserva_json["id"])
    assert reserva_guardada is not None
    assert reserva_guardada.token_cancelacion_hash != reserva_json["token_cancelacion"]

    cancelada = client.post(
        f"/api/v1/reservas/{reserva_json['id']}/cancelar",
        json={"token_cancelacion": reserva_json["token_cancelacion"]},
    )
    assert cancelada.status_code == 200
    assert cancelada.json()["estado"] == "cancelada"
