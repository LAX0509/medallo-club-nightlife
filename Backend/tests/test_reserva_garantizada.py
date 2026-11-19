import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models.invitado_model import InvitadoModel
from app.infrastructure.models.notificacion_model import NotificacionModel
from app.infrastructure.models.reserva_model import ReservaModel


@pytest.fixture(autouse=True)
def _whatsapp_simulado(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    confirmaciones: list[dict] = []
    monkeypatch.setattr("app.api.v1.reservas_router.notificar_nueva_reserva", lambda _d: None)

    def confirmar(datos: dict):
        confirmaciones.append(datos)
        return ("enviada", None, f"wamid.{len(confirmaciones)}")

    monkeypatch.setattr("app.api.v1.reservas_router.notificar_confirmacion_reserva", confirmar)
    return confirmaciones


def _solicitar(client: TestClient, evento_id: int, asistentes: int = 3, promotor_id: int | None = None) -> dict:
    cuerpo = {
        "evento_id": evento_id, "nombre_cliente": "Camila Ríos", "telefono": "+57 300 123 4567",
        "tipo": "mesa", "asistentes": asistentes,
    }
    if promotor_id:
        cuerpo["promotor_id"] = promotor_id
    respuesta = client.post("/api/v1/reservas", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_confirmar_garantiza_con_codigo_condiciones_y_pases(
    client: TestClient, auth, crear_evento, _whatsapp_simulado, db_session: Session
) -> None:
    evento = crear_evento(aforo=50)
    reserva = _solicitar(client, evento["id"], asistentes=3)
    assert reserva["garantizada"] is False and reserva["codigo_garantia"] is None

    confirmada = client.patch(
        f"/api/v1/reservas/{reserva['id']}/estado",
        json={"estado": "confirmada", "ubicacion_asignada": "Mesa 12 · terraza", "hora_limite": "23:30", "consumo_minimo": "600000"},
        headers=auth,
    )
    assert confirmada.status_code == 200, confirmada.text
    datos = confirmada.json()
    assert datos["garantizada"] is True
    assert datos["codigo_garantia"].startswith(f"MC-{reserva['id']:05d}-")
    assert (datos["hora_limite"], datos["ubicacion_asignada"]) == ("23:30", "Mesa 12 · terraza")
    assert float(datos["consumo_minimo"]) == 600000
    assert (datos["pases_total"], datos["pases_usados"]) == (3, 0)
    assert datos["whatsapp_confirmacion_estado"] == "enviada"

    # El aviso al cliente lleva el código de garantía en lugar del número simple.
    assert _whatsapp_simulado[0]["id"] == datos["codigo_garantia"]

    pases = client.get(f"/api/v1/reservas/{reserva['id']}/pases", headers=auth).json()
    assert [p["nombre"] for p in pases] == ["Camila Ríos", "Invitado 2 de Camila Ríos", "Invitado 3 de Camila Ríos"]
    assert len({p["qr_code"] for p in pases}) == 3

    # Confirmar de nuevo es idempotente: no duplica pases ni reenvía el aviso.
    otra = client.patch(f"/api/v1/reservas/{reserva['id']}/estado", json={"estado": "confirmada"}, headers=auth)
    assert otra.status_code == 200
    assert len(client.get(f"/api/v1/reservas/{reserva['id']}/pases", headers=auth).json()) == 3
    assert len(_whatsapp_simulado) == 1


def test_no_garantiza_si_no_hay_cupo_salvo_que_se_fuerce(client: TestClient, auth, crear_evento) -> None:
    evento = crear_evento(aforo=5)
    reserva = _solicitar(client, evento["id"], asistentes=6)
    sin_cupo = client.patch(f"/api/v1/reservas/{reserva['id']}/estado", json={"estado": "confirmada"}, headers=auth)
    assert sin_cupo.status_code == 409
    assert "cupo" in sin_cupo.json()["detail"].lower()
    forzada = client.patch(
        f"/api/v1/reservas/{reserva['id']}/estado", json={"estado": "confirmada", "forzar_cupo": True}, headers=auth
    )
    assert forzada.status_code == 200 and forzada.json()["pases_total"] == 6


def test_hora_limite_invalida_es_rechazada(client: TestClient, auth, crear_evento) -> None:
    reserva = _solicitar(client, crear_evento()["id"])
    respuesta = client.patch(
        f"/api/v1/reservas/{reserva['id']}/estado", json={"estado": "confirmada", "hora_limite": "25:99"}, headers=auth
    )
    assert respuesta.status_code == 422


def test_el_cliente_ve_su_reserva_garantizada_con_el_token(client: TestClient, auth, crear_evento) -> None:
    reserva = _solicitar(client, crear_evento(tematica="Retro")["id"], asistentes=2)
    token = reserva["token_cancelacion"]
    antes = client.post(f"/api/v1/reservas/{reserva['id']}/mi-reserva", json={"token_cancelacion": token}).json()
    assert antes["estado"] == "pendiente" and antes["garantizada"] is False and antes["pases"] == []

    client.patch(f"/api/v1/reservas/{reserva['id']}/estado", json={"estado": "confirmada", "hora_limite": "00:30"}, headers=auth)
    despues = client.post(f"/api/v1/reservas/{reserva['id']}/mi-reserva", json={"token_cancelacion": token}).json()
    assert despues["garantizada"] is True and despues["hora_limite"] == "00:30"
    assert len(despues["pases"]) == 2 and despues["puede_cancelar"] is True

    assert client.post(f"/api/v1/reservas/{reserva['id']}/mi-reserva", json={"token_cancelacion": "x" * 40}).status_code == 404


def test_pase_publico_muestra_la_garantia_y_sirve_en_puerta(client: TestClient, auth, crear_evento, crear_usuario) -> None:
    puerta = crear_usuario("puerta@nightlife.io", "Puerta")
    evento = crear_evento()
    reserva = _solicitar(client, evento["id"], asistentes=2)
    client.patch(f"/api/v1/reservas/{reserva['id']}/estado", json={"estado": "confirmada", "ubicacion_asignada": "Palco 3"}, headers=auth)
    pase = client.get(f"/api/v1/reservas/{reserva['id']}/pases", headers=auth).json()[0]

    publico = client.get(f"/api/v1/pases/{pase['qr_code']}")
    assert publico.status_code == 200
    cuerpo = publico.json()
    assert cuerpo["valido"] is True and cuerpo["reserva"]["ubicacion_asignada"] == "Palco 3"
    assert cuerpo["reserva"]["codigo_garantia"].startswith("MC-")

    ingreso = client.post("/api/v1/accesos", json={"evento_id": evento["id"], "qr_code": pase["qr_code"]}, headers=puerta["headers"])
    assert ingreso.status_code == 201 and ingreso.json()["acceso"]["resultado"] == "valido"
    assert client.get(f"/api/v1/pases/{pase['qr_code']}").json()["valido"] is False  # ya usado

    # Con un invitado dentro ya no se puede cancelar la reserva.
    token = reserva["token_cancelacion"]
    bloqueada = client.post(f"/api/v1/reservas/{reserva['id']}/cancelar", json={"token_cancelacion": token})
    assert bloqueada.status_code == 409 and "ingresaron" in bloqueada.json()["detail"]


def test_cancelar_una_reserva_garantizada_libera_los_pases(
    client: TestClient, auth, crear_evento, db_session: Session
) -> None:
    reserva = _solicitar(client, crear_evento()["id"], asistentes=4)
    client.patch(f"/api/v1/reservas/{reserva['id']}/estado", json={"estado": "confirmada"}, headers=auth)
    assert db_session.execute(select(InvitadoModel).where(InvitadoModel.reserva_id == reserva["id"])).scalars().all()

    cancelada = client.post(f"/api/v1/reservas/{reserva['id']}/cancelar", json={"token_cancelacion": reserva["token_cancelacion"]})
    assert cancelada.status_code == 200 and cancelada.json()["estado"] == "cancelada"
    db_session.expire_all()
    assert db_session.execute(select(InvitadoModel).where(InvitadoModel.reserva_id == reserva["id"])).scalars().all() == []
    # El equipo recibe un aviso de nivel "alerta" porque estaba garantizada.
    aviso = db_session.execute(select(NotificacionModel).where(NotificacionModel.tipo == "reserva_cancelada")).scalar_one()
    assert aviso.nivel == "alerta"


def test_el_promotor_referido_recibe_aviso_de_la_garantia(
    client: TestClient, auth, crear_evento, crear_usuario, db_session: Session
) -> None:
    promotor = crear_usuario("promo@nightlife.io", "Promotor")
    reserva = _solicitar(client, crear_evento()["id"], asistentes=2, promotor_id=promotor["id"])
    client.patch(f"/api/v1/reservas/{reserva['id']}/estado", json={"estado": "confirmada"}, headers=auth)
    pases = client.get(f"/api/v1/invitados?promotor_id={promotor['id']}", headers=promotor["headers"]).json()
    assert pases["total"] == 2  # los pases cuentan en las listas (y comisiones) del promotor

    avisos = client.get("/api/v1/notificaciones", headers=promotor["headers"]).json()
    assert avisos["no_leidas"] == 1 and avisos["items"][0]["tipo"] == "reserva_garantizada"
    # Un promotor no ve las notificaciones del equipo administrativo.
    assert all(i["tipo"] != "reserva_nueva" for i in avisos["items"])


def test_no_se_puede_volver_a_pendiente_una_reserva_garantizada(client: TestClient, auth, crear_evento) -> None:
    reserva = _solicitar(client, crear_evento()["id"])
    client.patch(f"/api/v1/reservas/{reserva['id']}/estado", json={"estado": "confirmada"}, headers=auth)
    respuesta = client.patch(f"/api/v1/reservas/{reserva['id']}/estado", json={"estado": "pendiente"}, headers=auth)
    assert respuesta.status_code == 409
