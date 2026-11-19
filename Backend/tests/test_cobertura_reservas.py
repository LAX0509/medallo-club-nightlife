"""Reservas de mesas y palcos: solicitud pública, vista privada del cliente, garantía, cancelación y reglas del servicio."""
import pytest

from app.application import reserva_service
from app.core.exceptions import ConflictError, NotFoundError
from app.infrastructure.models.reserva_model import ReservaModel

API = "/api/v1"


@pytest.fixture(autouse=True)
def _sin_avisos(monkeypatch):
    avisos = []
    monkeypatch.setattr("app.api.v1.reservas_router.notificar_nueva_reserva", lambda d: avisos.append(d))
    monkeypatch.setattr("app.api.v1.reservas_router.notificar_confirmacion_reserva", lambda d: ("enviada", None, "wamid.r1"))
    return avisos


def _solicitar(client, evento_id, **extra):
    cuerpo = {"evento_id": evento_id, "nombre_cliente": "Ana Torres", "telefono": "+57 300 123 4567", "tipo": "mesa", "asistentes": 3, **extra}
    r = client.post(f"{API}/reservas", json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()


def test_eventos_publicos_para_reservar(client, crear_evento):
    crear_evento("Abierto", dias=3, tematica="Retro")
    assert [e["nombre"] for e in client.get(f"{API}/reservas/eventos").json()] == ["Abierto"]


def test_solicitud_con_promotor_aviso_y_validaciones(client, auth, crear_evento, crear_usuario, _sin_avisos):
    evento = crear_evento()
    promotor = crear_usuario("pro@nightlife.io", "Promotor")
    r = _solicitar(client, evento["id"], promotor_id=promotor["id"], notas="  cumpleaños  ")
    assert r["notas"] == "cumpleaños" and r["estado"] == "pendiente" and len(r["token_cancelacion"]) >= 32
    assert _sin_avisos[-1]["promotor"] == promotor["nombre"] and _sin_avisos[-1]["tipo"] == "Mesa"
    directa = _solicitar(client, evento["id"], tipo="palco")
    assert _sin_avisos[-1]["promotor"] == "Solicitud directa" and _sin_avisos[-1]["tipo"] == "Palco" and _sin_avisos[-1]["notas"] == "Sin observaciones"
    assert directa["notas"] is None

    cuerpo = {"evento_id": evento["id"], "nombre_cliente": "Ana", "telefono": "3001234567", "tipo": "mesa", "asistentes": 2}
    assert client.post(f"{API}/reservas", json={**cuerpo, "evento_id": 9999}).status_code == 404
    # el id de promotor debe corresponder a un promotor activo
    admin_id = client.get(f"{API}/usuarios/me", headers=auth).json()["id"]
    assert client.post(f"{API}/reservas", json={**cuerpo, "promotor_id": admin_id}).status_code == 422
    assert client.post(f"{API}/reservas", json={**cuerpo, "promotor_id": 9999}).status_code == 422
    client.put(f"{API}/usuarios/{promotor['id']}", json={"estado": False}, headers=auth)
    assert client.post(f"{API}/reservas", json={**cuerpo, "promotor_id": promotor["id"]}).status_code == 422
    # esquema
    assert client.post(f"{API}/reservas", json={**cuerpo, "asistentes": 0}).status_code == 422
    assert client.post(f"{API}/reservas", json={**cuerpo, "asistentes": 51}).status_code == 422
    assert client.post(f"{API}/reservas", json={**cuerpo, "telefono": "abc-defg"}).status_code == 422
    # evento cerrado: no recibe solicitudes
    client.put(f"{API}/eventos/{evento['id']}", json={"estado": "cerrado"}, headers=auth)
    assert client.post(f"{API}/reservas", json=cuerpo).status_code == 404


def test_vista_privada_del_cliente_y_cancelacion_con_token(client, auth, crear_evento):
    evento = crear_evento()
    r = _solicitar(client, evento["id"])
    rid, token = r["id"], r["token_cancelacion"]
    mala = "x" * 40
    assert client.post(f"{API}/reservas/{rid}/mi-reserva", json={"token_cancelacion": mala}).status_code == 404
    assert client.post(f"{API}/reservas/9999/mi-reserva", json={"token_cancelacion": token}).status_code == 404
    assert client.post(f"{API}/reservas/{rid}/mi-reserva", json={"token_cancelacion": "corto"}).status_code == 422

    vista = client.post(f"{API}/reservas/{rid}/mi-reserva", json={"token_cancelacion": token}).json()
    assert vista["estado"] == "pendiente" and vista["pases"] == [] and vista["puede_cancelar"] is True and vista["garantizada"] is False

    # una vez garantizada, el cliente ve sus pases QR
    client.patch(f"{API}/reservas/{rid}/estado", json={"estado": "confirmada", "ubicacion_asignada": "  Palco 2  ", "hora_limite": "23:30", "consumo_minimo": "150000"}, headers=auth)
    vista = client.post(f"{API}/reservas/{rid}/mi-reserva", json={"token_cancelacion": token}).json()
    assert vista["garantizada"] and len(vista["pases"]) == 3 and vista["ubicacion_asignada"] == "Palco 2" and vista["hora_limite"] == "23:30"
    assert vista["codigo_garantia"].startswith("MC-")

    # con un pase usado ya no se puede cancelar
    from tests.conftest import _TestingSessionLocal

    with _TestingSessionLocal() as db:
        pase = reserva_service.pases_de(db, rid)[0]
        pase.estado = "usado"
        db.commit()
    vista = client.post(f"{API}/reservas/{rid}/mi-reserva", json={"token_cancelacion": token}).json()
    assert vista["puede_cancelar"] is False
    assert client.post(f"{API}/reservas/{rid}/cancelar", json={"token_cancelacion": token}).status_code == 409

    otra = _solicitar(client, evento["id"])
    assert client.post(f"{API}/reservas/{otra['id']}/cancelar", json={"token_cancelacion": mala}).status_code == 404
    ok = client.post(f"{API}/reservas/{otra['id']}/cancelar", json={"token_cancelacion": otra["token_cancelacion"]})
    assert ok.status_code == 200 and ok.json()["estado"] == "cancelada"
    assert client.post(f"{API}/reservas/{otra['id']}/cancelar", json={"token_cancelacion": otra["token_cancelacion"]}).status_code == 409
    vista = client.post(f"{API}/reservas/{otra['id']}/mi-reserva", json={"token_cancelacion": otra["token_cancelacion"]}).json()
    assert vista["puede_cancelar"] is False


def test_listados_de_admin_y_de_promotor(client, auth, crear_evento, crear_usuario):
    evento = crear_evento()
    pro = crear_usuario("pro@nightlife.io", "Promotor")
    otro = crear_usuario("otro@nightlife.io", "Promotor")
    r1 = _solicitar(client, evento["id"], promotor_id=pro["id"])
    _solicitar(client, evento["id"], promotor_id=otro["id"])
    _solicitar(client, evento["id"])
    client.patch(f"{API}/reservas/{r1['id']}/estado", json={"estado": "confirmada"}, headers=auth)

    todas = client.get(f"{API}/reservas", headers=auth).json()
    assert len(todas) == 3 and {r["promotor_nombre"] for r in todas} == {"Pro", "Otro", None}
    garantizada = next(r for r in todas if r["id"] == r1["id"])
    assert garantizada["garantizada"] and garantizada["pases_total"] == 3 and garantizada["pases_usados"] == 0
    suyas = client.get(f"{API}/reservas/mis-referidas", headers=pro["headers"]).json()
    assert [r["id"] for r in suyas] == [r1["id"]]
    assert client.get(f"{API}/reservas/mis-referidas", headers=auth).status_code == 403
    assert client.get(f"{API}/reservas", headers=pro["headers"]).status_code == 403
    assert client.get(f"{API}/reservas/mis-referidas", headers=otro["headers"]).json()[0]["pases_total"] == 0


def test_pases_de_reserva_y_estado_inexistente(client, auth, crear_evento):
    evento = crear_evento()
    r = _solicitar(client, evento["id"])
    assert client.get(f"{API}/reservas/{r['id']}/pases", headers=auth).json() == []
    assert client.get(f"{API}/reservas/9999/pases", headers=auth).status_code == 404
    assert client.patch(f"{API}/reservas/9999/estado", json={"estado": "confirmada"}, headers=auth).status_code == 404
    assert client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "confirmada", "hora_limite": "25:99"}, headers=auth).status_code == 422
    assert client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "confirmada", "hora_limite": "  "}, headers=auth).status_code == 200


def test_estados_pendiente_cancelada_y_reglas_de_la_garantia(client, auth, crear_evento):
    evento = crear_evento(aforo=5)
    r = _solicitar(client, evento["id"], asistentes=3)
    # pendiente -> pendiente es válido mientras no esté garantizada
    assert client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "pendiente"}, headers=auth).json()["estado"] == "pendiente"
    # confirmar garantiza (emite pases) y es idempotente: no reenvía el aviso ni duplica pases
    g1 = client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "confirmada"}, headers=auth).json()
    assert g1["garantizada"] and g1["whatsapp_confirmacion_estado"] == "enviada"
    g2 = client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "confirmada"}, headers=auth).json()
    assert g2["codigo_garantia"] == g1["codigo_garantia"] and g2["pases_total"] == 3
    # una garantizada no vuelve a pendiente
    assert client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "pendiente"}, headers=auth).status_code == 409

    # sin cupo: 3 + 3 > 5; con forzar_cupo se permite
    r2 = _solicitar(client, evento["id"], asistentes=3)
    sin_cupo = client.patch(f"{API}/reservas/{r2['id']}/estado", json={"estado": "confirmada"}, headers=auth)
    assert sin_cupo.status_code == 409 and "No hay cupo suficiente" in sin_cupo.json()["detail"]
    assert client.patch(f"{API}/reservas/{r2['id']}/estado", json={"estado": "confirmada", "forzar_cupo": True}, headers=auth).status_code == 200

    # cancelar libera los pases; cancelar dos veces no falla; una cancelada no se puede garantizar
    c1 = client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "cancelada"}, headers=auth).json()
    assert c1["estado"] == "cancelada" and c1["pases_total"] == 0
    assert client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "cancelada"}, headers=auth).status_code == 200
    assert client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "confirmada"}, headers=auth).status_code == 409


def test_reenviar_confirmacion_y_eliminar_reservas(client, auth, crear_evento):
    evento = crear_evento()
    r = _solicitar(client, evento["id"])
    assert client.post(f"{API}/reservas/9999/reenviar-confirmacion", headers=auth).status_code == 404
    assert client.post(f"{API}/reservas/{r['id']}/reenviar-confirmacion", headers=auth).status_code == 409  # aún pendiente
    client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "confirmada"}, headers=auth)
    reenviada = client.post(f"{API}/reservas/{r['id']}/reenviar-confirmacion", headers=auth)
    assert reenviada.status_code == 200 and reenviada.json()["whatsapp_confirmacion_estado"] == "enviada"

    # eliminar: solo canceladas
    assert client.delete(f"{API}/reservas/9999", headers=auth).status_code == 404
    assert client.delete(f"{API}/reservas/{r['id']}", headers=auth).status_code == 409
    client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "cancelada"}, headers=auth)
    assert client.delete(f"{API}/reservas/{r['id']}", headers=auth).status_code == 204
    assert len(client.get(f"{API}/reservas", headers=auth).json()) == 0


def test_la_reserva_reflejada_en_el_dashboard_de_aforo(client, auth, crear_evento):
    evento = crear_evento(aforo=10)
    r = _solicitar(client, evento["id"], asistentes=4)
    client.patch(f"{API}/reservas/{r['id']}/estado", json={"estado": "confirmada"}, headers=auth)
    assert client.get(f"{API}/invitados/resumen?evento_id={evento['id']}", headers=auth).json()["total"] == 4


# ------------------------------------------------------------------ servicio (unitario)
def test_servicio_token_telefonos_y_codigo_unico(db_session, monkeypatch):
    r = ReservaModel(evento_id=1, nombre_cliente="x", telefono="1", tipo="mesa", asistentes=1)
    assert reserva_service.token_valido(r, "algo") is False  # sin hash guardado
    r.token_cancelacion_hash = reserva_service.hash_token("secreto")
    assert reserva_service.token_valido(r, "secreto") and not reserva_service.token_valido(r, "") and not reserva_service.token_valido(r, "otro")

    assert reserva_service.coincide_telefono("+57 300 123 4567", "3001234567")
    assert not reserva_service.coincide_telefono("123", "123")  # demasiado corto
    assert not reserva_service.coincide_telefono("3001234567", "3001234568")
    assert reserva_service.digitos(None) == ""

    # si el código aleatorio chocara 10 veces seguidas, se informa un conflicto en lugar de duplicar
    db_session.add(ReservaModel(evento_id=1, nombre_cliente="x", telefono="1", tipo="mesa", asistentes=1, codigo_garantia="MC-00001-ABCD"))
    db_session.commit()
    monkeypatch.setattr(reserva_service.secrets, "token_hex", lambda n: "abcd")
    with pytest.raises(ConflictError):
        reserva_service._codigo_garantia_unico(db_session, 1)


def test_servicio_garantizar_sin_evento_y_liberar_con_pases_usados(db_session):
    huerfana = ReservaModel(evento_id=12345, nombre_cliente="x", telefono="3001234567", tipo="mesa", asistentes=1)
    db_session.add(huerfana)
    db_session.commit()
    with pytest.raises(NotFoundError):
        reserva_service.garantizar(db_session, huerfana, admin_id=1)
    assert reserva_service.liberar(db_session, huerfana) == 0


def test_reserva_huerfana_cuyo_evento_ya_no_existe_responde_404_en_todos_los_endpoints(client, auth, db_session):
    """Defensa ante datos inconsistentes (evento borrado a mano): ningún endpoint debe fallar con 500."""
    token = "t" * 40
    r = ReservaModel(evento_id=424242, nombre_cliente="x", telefono="3001234567", tipo="mesa", asistentes=1,
                     estado="confirmada", token_cancelacion_hash=reserva_service.hash_token(token))
    db_session.add(r)
    db_session.commit()
    rid = r.id
    assert client.post(f"{API}/reservas/{rid}/mi-reserva", json={"token_cancelacion": token}).status_code == 404
    assert client.post(f"{API}/reservas/{rid}/cancelar", json={"token_cancelacion": token}).status_code == 404
    assert client.patch(f"{API}/reservas/{rid}/estado", json={"estado": "cancelada"}, headers=auth).status_code == 404
    assert client.post(f"{API}/reservas/{rid}/reenviar-confirmacion", headers=auth).status_code == 404
