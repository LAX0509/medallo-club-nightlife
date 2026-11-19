"""Webhook de WhatsApp: verificación, firma HMAC, estados de entrega de Meta y procesamiento de mensajes entrantes."""
import hashlib
import hmac
import json
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.reserva_model import ReservaModel
from app.infrastructure.models.usuario_model import UsuarioModel
from app.infrastructure.models.whatsapp_estado_model import WhatsAppEstadoModel
from app.infrastructure.models.whatsapp_inbound_message_model import WhatsAppInboundMessageModel

SECRETO = "secreto-de-prueba"


@pytest.fixture
def ajustes(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "whatsapp_app_secret", SECRETO)
    monkeypatch.setattr(s, "whatsapp_webhook_verify_token", "verifica")
    monkeypatch.setattr(s, "whatsapp_reservation_page_url", "https://club.example/reservas")
    return s


@pytest.fixture
def respuestas(monkeypatch):
    enviadas = []

    def _responder(telefono, texto):
        enviadas.append((telefono, texto))
        return ("respondido", None)

    monkeypatch.setattr("app.api.v1.whatsapp_router.responder_mensaje_bot_whatsapp", _responder)
    return enviadas


@pytest.fixture
def avisos(monkeypatch):
    lista = []
    monkeypatch.setattr("app.api.v1.whatsapp_router.notificar_nueva_reserva", lambda d: lista.append(d))
    return lista


def _firmar(cuerpo: bytes, secreto: str = SECRETO) -> dict[str, str]:
    firma = "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return {"Content-Type": "application/json", "X-Hub-Signature-256": firma}


def _enviar(client, payload, secreto=SECRETO):
    cuerpo = json.dumps(payload).encode()
    return client.post("/webhooks/whatsapp", content=cuerpo, headers=_firmar(cuerpo, secreto))


def _con_mensajes(*mensajes):
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": list(mensajes)}}]}]}


def _con_estados(*estados):
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"statuses": list(estados)}}]}]}


def _texto(id_, de, cuerpo):
    return {"id": id_, "from": de, "type": "text", "text": {"body": cuerpo}}


# ------------------------------------------------------------------ verificación y salud
def test_verificacion_del_webhook(client, ajustes, monkeypatch):
    base = {"hub.mode": "subscribe", "hub.verify_token": "verifica", "hub.challenge": "abc"}
    assert client.get("/webhooks/whatsapp", params=base).text == "abc"
    assert client.get("/webhooks/whatsapp", params={**base, "hub.verify_token": "otro"}).status_code == 403
    assert client.get("/webhooks/whatsapp", params={**base, "hub.mode": "unsubscribe"}).status_code == 403
    sin_challenge = {k: v for k, v in base.items() if k != "hub.challenge"}
    assert client.get("/webhooks/whatsapp", params=sin_challenge).status_code == 403
    assert client.get("/webhooks/whatsapp").status_code == 403
    monkeypatch.setattr(ajustes, "whatsapp_webhook_verify_token", "")
    assert client.get("/webhooks/whatsapp", params=base).status_code == 503


def test_salud_del_webhook_refleja_la_configuracion(client, ajustes, monkeypatch):
    assert client.get("/webhooks/whatsapp/health").json() == {"verify_token": "configurado", "app_secret": "configurado"}
    monkeypatch.setattr(ajustes, "whatsapp_app_secret", "")
    monkeypatch.setattr(ajustes, "whatsapp_webhook_verify_token", "")
    assert client.get("/webhooks/whatsapp/health").json() == {"verify_token": "pendiente", "app_secret": "pendiente"}


# ------------------------------------------------------------------ firma y formato
def test_post_rechaza_sin_secreto_firma_mala_json_malo_y_formato_no_objeto(client, ajustes, monkeypatch):
    cuerpo = b'{"a": 1}'
    assert client.post("/webhooks/whatsapp", content=cuerpo, headers=_firmar(cuerpo, "otro-secreto")).status_code == 401
    assert client.post("/webhooks/whatsapp", content=cuerpo, headers={"Content-Type": "application/json"}).status_code == 401
    assert client.post("/webhooks/whatsapp", content=cuerpo, headers={"X-Hub-Signature-256": "md5=abc"}).status_code == 401
    malo = b"{no es json"
    r = client.post("/webhooks/whatsapp", content=malo, headers=_firmar(malo))
    assert r.status_code == 400 and "JSON válido" in r.json()["detail"]
    no_utf8 = b"\xff\xfe\x00"
    assert client.post("/webhooks/whatsapp", content=no_utf8, headers=_firmar(no_utf8)).status_code == 400
    lista = b"[1, 2]"
    assert client.post("/webhooks/whatsapp", content=lista, headers=_firmar(lista)).status_code == 400
    # un objeto de otra cuenta se acepta pero se ignora
    assert _enviar(client, {"object": "page", "entry": []}).json() == {"status": "ok"}
    monkeypatch.setattr(ajustes, "whatsapp_app_secret", "")
    assert client.post("/webhooks/whatsapp", content=cuerpo, headers=_firmar(cuerpo)).status_code == 503


# ------------------------------------------------------------------ estados de entrega
def _reserva_con_confirmacion(db_session, message_id="wamid.c1", estado="enviada"):
    admin = UsuarioModel(nombre="A", email="a@a.io", password_hash="x", rol="Administrador", estado=True)
    db_session.add(admin)
    db_session.commit()
    ev = EventoModel(administrador_id=admin.id, nombre="E", fecha=date.today() + timedelta(days=3), aforo_maximo=10, estado="planeado")
    db_session.add(ev)
    db_session.commit()
    r = ReservaModel(evento_id=ev.id, nombre_cliente="C", telefono="3001234567", tipo="mesa", asistentes=2, estado="confirmada",
                     whatsapp_confirmacion_message_id=message_id, whatsapp_confirmacion_estado=estado)
    db_session.add(r)
    db_session.commit()
    return r.id


def test_estados_de_entrega_se_guardan_y_actualizan_la_reserva_sin_retroceder(client, db_session, ajustes):
    rid = _reserva_con_confirmacion(db_session)

    def estado_reserva():
        db_session.expire_all()
        r = db_session.get(ReservaModel, rid)
        return r.whatsapp_confirmacion_estado, r.whatsapp_confirmacion_error

    _enviar(client, _con_estados({"id": "wamid.c1", "status": "read", "recipient_id": "573001234567"}))
    assert estado_reserva() == ("leida", None)
    # un «delivered» tardío no degrada «leida»
    _enviar(client, _con_estados({"id": "wamid.c1", "status": "delivered"}))
    assert estado_reserva()[0] == "leida"
    # un fallo siempre se registra, con el título del error de Meta
    _enviar(client, _con_estados({"id": "wamid.c1", "status": "failed", "recipient_id": "573001234567",
                                  "errors": [{"code": 131026, "title": "Receptor no disponible", "error_data": {"details": "sin WhatsApp"}}]}))
    assert estado_reserva() == ("fallida", "Receptor no disponible")
    _enviar(client, _con_estados({"id": "wamid.c1", "status": "failed"}))
    assert estado_reserva() == ("fallida", "Meta no pudo entregar la confirmación.")

    filas = db_session.execute(select(WhatsAppEstadoModel).order_by(WhatsAppEstadoModel.id)).scalars().all()
    assert [f.estado for f in filas] == ["read", "delivered", "failed", "failed"]
    assert filas[0].destinatario_fin == "4567"  # solo los últimos 4 dígitos
    assert (filas[2].codigo_error, filas[2].titulo_error, filas[2].detalle_error) == ("131026", "Receptor no disponible", "sin WhatsApp")
    assert filas[1].destinatario_fin is None and filas[1].codigo_error is None


def test_estados_invalidos_o_de_mensajes_ajenos_se_ignoran_o_solo_se_registran(client, db_session, ajustes):
    _enviar(client, _con_estados({"status": "delivered"}, {"id": "x", "status": "inventado"}, {"id": "", "status": "sent"}))
    assert db_session.execute(select(WhatsAppEstadoModel)).scalars().all() == []
    # mensaje que no es de ninguna reserva: queda registrado (sirve al diagnóstico) sin tocar reservas
    _enviar(client, _con_estados({"id": "wamid.otro", "status": "sent", "errors": ["no-dict"]}))
    fila = db_session.execute(select(WhatsAppEstadoModel)).scalar_one()
    assert fila.message_id == "wamid.otro" and fila.codigo_error is None
    # «sent» sobre una reserva ya «entregada» no retrocede
    rid = _reserva_con_confirmacion(db_session, "wamid.c2", estado="entregada")
    _enviar(client, _con_estados({"id": "wamid.c2", "status": "sent"}))
    db_session.expire_all()
    assert db_session.get(ReservaModel, rid).whatsapp_confirmacion_estado == "entregada"


# ------------------------------------------------------------------ mensajes entrantes
def test_tipos_de_mensaje_texto_boton_e_interactivo(client, db_session, ajustes, respuestas):
    mensajes = [
        _texto("w1", "573001111111", "hola"),
        {"id": "w2", "from": "573002222222", "type": "button", "button": {"text": "Ver eventos"}},
        {"id": "w3", "from": "573003333333", "type": "interactive", "interactive": {"button_reply": {"title": "Horario"}}},
        {"id": "w4", "from": "573004444444", "type": "interactive", "interactive": {"list_reply": {"title": "Ubicación"}}},
    ]
    assert _enviar(client, _con_mensajes(*mensajes)).status_code == 200
    assert len(respuestas) == 4
    assert "horario" in respuestas[2][1].lower() and "estamos en" in respuestas[3][1].lower()
    filas = db_session.execute(select(WhatsAppInboundMessageModel)).scalars().all()
    assert len(filas) == 4 and all(f.response_status == "respondido" for f in filas)
    # el teléfono no se guarda: solo su hash
    assert filas[0].sender_hash == hashlib.sha256(b"573001111111").hexdigest()


def test_mensaje_sin_texto_responde_que_solo_entiende_texto(client, db_session, ajustes, respuestas):
    _enviar(client, _con_mensajes({"id": "img1", "from": "573001111111", "type": "image"}))
    assert len(respuestas) == 1 and "mensajes de texto" in respuestas[0][1]
    fila = db_session.get(WhatsAppInboundMessageModel, "img1")
    assert fila.sentiment and fila.response_status == "respondido"


def test_mensajes_sin_id_o_remitente_y_duplicados_no_se_procesan(client, db_session, ajustes, respuestas):
    _enviar(client, _con_mensajes({"from": "573001111111", "type": "text", "text": {"body": "hola"}},
                                  {"id": "sin-from", "type": "text", "text": {"body": "hola"}}))
    assert respuestas == []
    msg = _texto("dup1", "573001111111", "hola")
    _enviar(client, _con_mensajes(msg))
    _enviar(client, _con_mensajes(msg))  # Meta reintenta la entrega
    assert len(respuestas) == 1


def test_reintento_tras_respuesta_fallida_solo_reenvia_un_mensaje_seguro(client, db_session, ajustes, monkeypatch):
    estados = iter([("fallida", "Meta caído"), ("fallida", "Meta caído"), ("respondido", None)])
    enviados = []

    def _responder(tel, texto):
        enviados.append(texto)
        return next(estados)

    monkeypatch.setattr("app.api.v1.whatsapp_router.responder_mensaje_bot_whatsapp", _responder)
    msg = _texto("re1", "573001111111", "hola")
    _enviar(client, _con_mensajes(msg))
    assert db_session.get(WhatsAppInboundMessageModel, "re1").response_status == "fallida"
    _enviar(client, _con_mensajes(msg))  # reintento: sigue fallando
    assert "Escribe MENÚ" in enviados[1]
    _enviar(client, _con_mensajes(msg))  # reintento exitoso
    db_session.expire_all()
    assert db_session.get(WhatsAppInboundMessageModel, "re1").response_status == "respondido"
    assert len(db_session.execute(select(WhatsAppInboundMessageModel)).scalars().all()) == 1  # no se duplicó el asistente


def test_reserva_completa_por_whatsapp_avisa_al_equipo(client, db_session, ajustes, respuestas, avisos):
    admin = UsuarioModel(nombre="A", email="a@a.io", password_hash="x", rol="Administrador", estado=True)
    db_session.add(admin)
    db_session.commit()
    db_session.add(EventoModel(administrador_id=admin.id, nombre="Noche Retro", fecha=date.today() + timedelta(days=4), aforo_maximo=50, estado="planeado"))
    db_session.commit()
    remitente = "573009998877"
    for i, texto in enumerate(["quiero reservar una mesa para 4 personas", "Laura Gómez", "sin notas", "sí"]):
        _enviar(client, _con_mensajes(_texto(f"flujo{i}", remitente, texto)))
    reserva = db_session.execute(select(ReservaModel)).scalar_one()
    assert (reserva.nombre_cliente, reserva.asistentes, reserva.telefono) == ("Laura Gómez", 4, "+573009998877")
    assert len(avisos) == 1 and avisos[0]["id"] == reserva.id
    assert "Sigue o gestiona tu reserva aquí" in respuestas[-1][1]


def test_dos_entregas_simultaneas_del_mismo_mensaje_no_duplican_la_respuesta(client, db_session, ajustes, respuestas, monkeypatch):
    """Si otro proceso insertó el mismo message_id entre la comprobación y el commit, se descarta sin responder."""
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    original = Session.commit
    estado = {"fallar": True}

    def _commit(self):
        nuevos = [o for o in self.new if isinstance(o, WhatsAppInboundMessageModel)]
        if nuevos and estado["fallar"]:
            estado["fallar"] = False
            self.rollback()
            raise IntegrityError("INSERT", {}, Exception("duplicado"))
        return original(self)

    monkeypatch.setattr(Session, "commit", _commit)
    _enviar(client, _con_mensajes(_texto("carrera1", "573001111111", "hola")))
    monkeypatch.setattr(Session, "commit", original)
    assert respuestas == []
    assert db_session.get(WhatsAppInboundMessageModel, "carrera1") is None


def test_el_bot_no_pudo_responder_se_registra_el_estado(client, db_session, ajustes, monkeypatch):
    monkeypatch.setattr("app.api.v1.whatsapp_router.responder_mensaje_bot_whatsapp", lambda t, x: ("sin_configurar", "faltan credenciales"))
    _enviar(client, _con_mensajes(_texto("sc1", "573001111111", "hola")))
    assert db_session.get(WhatsAppInboundMessageModel, "sc1").response_status == "sin_configurar"
