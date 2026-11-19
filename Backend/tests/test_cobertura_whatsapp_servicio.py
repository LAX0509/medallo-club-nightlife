"""Servicio de WhatsApp: toda la comunicación con Meta se simula con respuestas ``httpx.Response`` reales
(código, JSON y ``raise_for_status`` auténticos); nunca se hace HTTP de verdad."""
import logging

import httpx
import pytest

from app.application import whatsapp_notification_service as wa
from app.core.config import get_settings
from app.infrastructure.models.whatsapp_estado_model import WhatsAppEstadoModel


@pytest.fixture
def config(monkeypatch):
    """Credenciales completas de prueba; devuelve el objeto de ajustes para cambiarlas por prueba."""
    s = get_settings()
    valores = {
        "whatsapp_phone_number_id": "1234567890",
        "whatsapp_access_token": "token-de-prueba",
        "whatsapp_notify_to": "573001112233, 573204445566",
        "whatsapp_template_name": "plantilla_reserva",
        "whatsapp_confirmation_template_name": "plantilla_confirma",
        "whatsapp_inventory_template_name": "plantilla_stock",
    }
    for k, v in valores.items():
        monkeypatch.setattr(s, k, v)
    return s


@pytest.fixture
def bd_de_pruebas(monkeypatch):
    """El servicio abre su propia sesión; se redirige a la base en memoria de las pruebas."""
    from tests.conftest import _TestingSessionLocal

    monkeypatch.setattr(wa, "_sesion_bd", _TestingSessionLocal)
    monkeypatch.setattr("time.sleep", lambda _s: None)


def _resp(status=200, json=None, texto=None, metodo="POST"):
    req = httpx.Request(metodo, "https://graph.facebook.com/test")
    if json is not None:
        return httpx.Response(status, json=json, request=req)
    return httpx.Response(status, text=texto or "", request=req)


def _post_ok(monkeypatch, message_id="wamid.OK", registro=None):
    def _post(url, headers=None, json=None, timeout=None):
        if registro is not None:
            registro.append((url, headers, json))
        return _resp(200, {"messages": [{"id": message_id}]})

    monkeypatch.setattr(wa.httpx, "post", _post)


# ------------------------------------------------------------------ utilidades
def test_destinatarios_normaliza_separadores_y_descarta_invalidos():
    assert wa.destinatarios("+57 300 111 2233; 573001112233\n(320) 444-5566, 123, ") == ["573001112233", "3204445566"]
    assert wa.destinatarios(None) == []
    assert wa._endpoint().endswith("/messages") and "graph.facebook.com" in wa._endpoint()


def test_error_de_meta_con_json_con_texto_y_con_detalle():
    r = _resp(400, {"error": {"code": 131030, "message": "No permitido", "error_data": {"details": "lista"}}})
    assert wa._error_de_meta(r) == ("131030", "No permitido — lista")
    assert wa._error_de_meta(_resp(500, texto="<html>caído</html>")) == ("?", "<html>caído</html>")
    assert wa._error_de_meta(_resp(500, texto="")) == ("?", "sin detalle")
    assert wa._error_de_meta(_resp(400, {})) == ("?", "sin detalle")


def test_causa_de_error_conocida_y_desconocida():
    assert "lista de destinatarios" in wa._causa_error_entrega("131030", None)
    assert wa._causa_error_entrega("999", "Título de Meta") == "Título de Meta"
    assert "no informó" in wa._causa_error_entrega(None, None)


# ------------------------------------------------------------------ _enviar_plantilla
def test_enviar_plantilla_sin_credenciales_o_telefono_malo(config, monkeypatch):
    assert wa._enviar_plantilla("", "es", "573001112233", [])[0] == "sin_configurar"
    estado, err, _ = wa._enviar_plantilla("p", "es", "123", [])
    assert estado == "fallida" and "formato internacional" in err
    monkeypatch.setattr(config, "whatsapp_access_token", "")
    assert wa._enviar_plantilla("p", "es", "573001112233", [])[0] == "sin_configurar"


def test_enviar_plantilla_exitosa_arma_el_cuerpo_correcto(config, monkeypatch):
    llamadas = []
    _post_ok(monkeypatch, "wamid.XYZ", llamadas)
    extra = [{"type": "button", "sub_type": "url", "index": "0", "parameters": []}]
    estado, err, mid = wa._enviar_plantilla("plantilla", "es", "+57 300 111 2233", ["a", "b"], componentes_extra=extra)
    assert (estado, err, mid) == ("enviada", None, "wamid.XYZ")
    url, headers, cuerpo = llamadas[0]
    assert url.endswith("/1234567890/messages") and headers["Authorization"] == "Bearer token-de-prueba"
    assert cuerpo["to"] == "573001112233" and cuerpo["template"]["name"] == "plantilla"
    assert cuerpo["template"]["components"][0]["parameters"] == [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
    assert cuerpo["template"]["components"][1] == extra[0]


def test_enviar_plantilla_errores_de_meta_y_de_red(config, monkeypatch, caplog):
    monkeypatch.setattr(wa.httpx, "post", lambda *a, **k: _resp(200, {"messages": []}))
    assert wa._enviar_plantilla("p", "es", "573001112233", [])[:2] == ("fallida", "Meta no devolvió un identificador de mensaje.")

    monkeypatch.setattr(wa.httpx, "post", lambda *a, **k: _resp(400, {"error": {"code": 132001, "message": "Sin plantilla"}}))
    with caplog.at_level(logging.ERROR):
        estado, err, mid = wa._enviar_plantilla("p", "es", "573001112233", [])
    assert estado == "fallida" and mid is None and "HTTP 400" in err and "132001" in err and "Sin plantilla" in err
    assert "token-de-prueba" not in err and "token-de-prueba" not in caplog.text  # nunca se filtra el token

    def _caida(*a, **k):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(wa.httpx, "post", _caida)
    assert wa._enviar_plantilla("p", "es", "573001112233", [])[1] == "No se pudo conectar con WhatsApp. Puedes reintentar."

    monkeypatch.setattr(wa.httpx, "post", lambda *a, **k: _resp(200, texto="no es json"))
    assert wa._enviar_plantilla("p", "es", "573001112233", [])[0] == "fallida"  # JSON inválido -> ValueError controlado


# ------------------------------------------------------------------ notificaciones
def test_confirmacion_de_reserva(config, monkeypatch):
    datos = {"nombre_cliente": "Ana", "evento_nombre": "Noche", "tipo": "Mesa", "asistentes": 4, "id": 77, "telefono": "573001112233"}
    llamadas = []
    _post_ok(monkeypatch, registro=llamadas)
    assert wa.notificar_confirmacion_reserva(datos) == ("enviada", None, "wamid.OK")
    params = [p["text"] for p in llamadas[0][2]["template"]["components"][0]["parameters"]]
    assert params == ["Ana", "Noche", "Mesa", "4", "77"]
    monkeypatch.setattr(config, "whatsapp_confirmation_template_name", "")
    assert wa.notificar_confirmacion_reserva(datos)[0] == "sin_configurar"


def test_stock_bajo_omitido_enviado_y_con_fallo(config, monkeypatch, caplog):
    datos = {"nombre": "Ron", "unidad": "botellas", "cantidad": 2, "stock_minimo": 5, "categoria": None}
    monkeypatch.setattr(config, "whatsapp_inventory_template_name", "")
    wa.notificar_stock_bajo(datos)  # sin plantilla: no hace nada ni llama a HTTP (el conftest lo haría fallar)

    monkeypatch.setattr(config, "whatsapp_inventory_template_name", "plantilla_stock")
    monkeypatch.setattr(config, "whatsapp_inventory_notify_to", "")
    llamadas = []
    _post_ok(monkeypatch, registro=llamadas)
    wa.notificar_stock_bajo(datos)
    assert len(llamadas) == 2  # cae al WHATSAPP_NOTIFY_TO (dos destinos)
    params = [p["text"] for p in llamadas[0][2]["template"]["components"][0]["parameters"]]
    assert params == ["Ron", "2 botellas", "5 botellas", "General"]

    monkeypatch.setattr(config, "whatsapp_inventory_notify_to", "573009998877")
    monkeypatch.setattr(wa.httpx, "post", lambda *a, **k: _resp(401, {"error": {"code": 190, "message": "vencido"}}))
    with caplog.at_level(logging.WARNING):
        wa.notificar_stock_bajo(datos)  # un fallo no lanza excepción
    assert "No se pudo avisar el stock bajo" in caplog.text


def test_respuesta_del_bot_por_whatsapp(config, monkeypatch):
    llamadas = []
    _post_ok(monkeypatch, registro=llamadas)
    assert wa.responder_mensaje_bot_whatsapp("+57 300 111 2233", "x" * 5000) == ("respondido", None)
    cuerpo = llamadas[0][2]
    assert cuerpo["type"] == "text" and len(cuerpo["text"]["body"]) == 4096 and cuerpo["to"] == "573001112233"
    assert wa.responder_mensaje_bot_whatsapp("12", "hola")[0] == "fallida"
    monkeypatch.setattr(wa.httpx, "post", lambda *a, **k: _resp(500, {"error": {}}))
    assert wa.responder_mensaje_bot_whatsapp("573001112233", "hola") == ("fallida", "Meta rechazó la respuesta (HTTP 500).")

    def _caida(*a, **k):
        raise httpx.ReadTimeout("lento")

    monkeypatch.setattr(wa.httpx, "post", _caida)
    assert wa.responder_mensaje_bot_whatsapp("573001112233", "hola") == ("fallida", "No se pudo conectar con WhatsApp.")
    monkeypatch.setattr(config, "whatsapp_access_token", "")
    assert wa.responder_mensaje_bot_whatsapp("573001112233", "hola")[0] == "sin_configurar"


def test_nueva_reserva_omitida_con_boton_y_con_destino_fallido(config, monkeypatch, caplog):
    datos = {"id": 5, "nombre_cliente": "Ana", "telefono": "300", "evento_nombre": "Noche", "tipo": "Mesa", "asistentes": 3, "promotor": "Pepe", "notas": "-"}
    monkeypatch.setattr(config, "whatsapp_notify_to", "")
    with caplog.at_level(logging.WARNING):
        wa.notificar_nueva_reserva(datos)
    assert "WHATSAPP_NOTIFY_TO" in caplog.text

    monkeypatch.setattr(config, "whatsapp_notify_to", "573001112233, 573204445566")
    monkeypatch.setattr(config, "whatsapp_reservation_url_prefix", "https://club/reservas/")
    llamadas = []

    def _post(url, headers=None, json=None, timeout=None):
        llamadas.append(json)
        if json["to"] == "573001112233":
            return _resp(400, {"error": {"code": 131030, "message": "no permitido"}})
        return _resp(200, {"messages": [{"id": "wamid.2"}]})

    monkeypatch.setattr(wa.httpx, "post", _post)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        wa.notificar_nueva_reserva(datos)
    assert [c["to"] for c in llamadas] == ["573001112233", "573204445566"]  # el fallo no impide avisar al segundo
    assert llamadas[0]["template"]["components"][1]["sub_type"] == "url"
    assert "No se pudo enviar el aviso de nueva reserva a ...2233" in caplog.text


def test_aviso_de_prueba(config, monkeypatch):
    llamadas = []
    _post_ok(monkeypatch, registro=llamadas)
    assert wa.enviar_aviso_prueba("+57 300 111 2233") == ("enviada", None)
    assert llamadas[0][2]["to"] == "573001112233"
    assert wa.enviar_aviso_prueba("1")[0] == "fallida"


# ------------------------------------------------------------------ estados de entrega y diagnóstico
def _guardar_estado(db, message_id, estado, codigo=None, titulo=None):
    db.add(WhatsAppEstadoModel(message_id=message_id, estado=estado, codigo_error=codigo, titulo_error=titulo))
    db.commit()


def test_ultimo_evento_y_espera_de_estados(bd_de_pruebas, db_session):
    assert wa._ultimo_evento_meta() is None
    _guardar_estado(db_session, "wamid.A", "sent")
    assert wa._ultimo_evento_meta() is not None
    # sin estado final: espera el plazo y devuelve lo que haya
    assert [e.estado for e in wa._esperar_estados("wamid.A", segundos=0)] == ["sent"]
    _guardar_estado(db_session, "wamid.A", "delivered")
    assert [e.estado for e in wa._esperar_estados("wamid.A", segundos=5)] == ["sent", "delivered"]
    assert wa._esperar_estados("wamid.NADA", segundos=0) == []


def test_ultimo_evento_y_estados_toleran_error_de_base(monkeypatch):
    def _rota():
        raise RuntimeError("sin tabla")

    monkeypatch.setattr(wa, "_sesion_bd", _rota)
    assert wa._ultimo_evento_meta() is None
    assert wa._esperar_estados("wamid.A", segundos=0) == []


def test_esperar_estados_reintenta_hasta_que_llega_el_estado_final(bd_de_pruebas, db_session, monkeypatch):
    pausas = []

    def _dormir(_s):
        pausas.append(1)
        _guardar_estado(db_session, "wamid.B", "read")

    monkeypatch.setattr("time.sleep", _dormir)
    eventos = wa._esperar_estados("wamid.B", segundos=30)
    assert len(pausas) == 1 and eventos[0].estado == "read"


class _Red:
    """Respuestas guiadas de la Graph API para ``httpx.get`` del diagnóstico."""

    def __init__(self, token=None, numero=None, error=None):
        self.token = token if token is not None else _resp(200, {"data": {"is_valid": True, "scopes": ["whatsapp_business_messaging"]}}, metodo="GET")
        self.numero = numero if numero is not None else _resp(200, {"display_phone_number": "+57 300", "verified_name": "Club", "quality_rating": "GREEN"}, metodo="GET")
        self.error = error

    def get(self, url, params=None, headers=None, timeout=None):
        if self.error:
            raise self.error
        return self.token if "debug_token" in url else self.numero


def test_diagnostico_sin_configuracion_se_detiene_en_el_primer_paso(monkeypatch):
    r = wa.diagnosticar_aviso_reserva()
    assert r["ok"] is False and len(r["pasos"]) == 1 and r["pasos"][0]["clave"] == "configuracion"
    assert "WHATSAPP_PHONE_NUMBER_ID" in r["pasos"][0]["detalle"]


def test_diagnostico_token_rechazado_invalido_sin_permisos_y_sin_red(config, monkeypatch):
    clave = lambda r: {p["clave"]: p for p in r["pasos"]}
    monkeypatch.setattr(wa.httpx, "get", _Red(token=_resp(400, {"error": {"code": 190, "message": "vencido"}}, metodo="GET")).get)
    r = wa.diagnosticar_aviso_reserva()
    assert not r["ok"] and not clave(r)["token"]["ok"] and "190" in clave(r)["token"]["detalle"]

    monkeypatch.setattr(wa.httpx, "get", _Red(token=_resp(200, {"data": {"is_valid": False}}, metodo="GET")).get)
    assert "no es válido" in clave(wa.diagnosticar_aviso_reserva())["token"]["detalle"]

    # token válido pero sin el permiso: el diagnóstico sigue, así que el envío (simulado) también se ejecuta
    monkeypatch.setattr(wa.httpx, "get", _Red(token=_resp(200, {"data": {"is_valid": True, "scopes": ["otro"], "expires_at": 1}}, metodo="GET")).get)
    monkeypatch.setattr(wa.httpx, "post", lambda *a, **k: _resp(400, {"error": {"code": 1, "message": "x"}}))
    monkeypatch.setattr(wa, "_sesion_bd", lambda: (_ for _ in ()).throw(RuntimeError("sin bd")))
    r = wa.diagnosticar_aviso_reserva()
    assert not clave(r)["token"]["ok"] and "whatsapp_business_messaging" in clave(r)["token"]["detalle"]

    monkeypatch.setattr(wa.httpx, "get", _Red(numero=_resp(404, {"error": {"code": 100, "message": "no existe"}}, metodo="GET")).get)
    r = wa.diagnosticar_aviso_reserva()
    assert not r["ok"] and "no existe" in clave(r)["numero"]["detalle"]

    monkeypatch.setattr(wa.httpx, "get", _Red(error=httpx.ConnectError("x")).get)
    r = wa.diagnosticar_aviso_reserva()
    assert not r["ok"] and "ConnectError" in clave(r)["red"]["detalle"]


def _diagnostico_completo(monkeypatch, db_session, *, webhook_previo, estados_por_mensaje, aceptar_envio=True):
    from tests.conftest import _TestingSessionLocal

    monkeypatch.setattr(wa, "_sesion_bd", _TestingSessionLocal)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    monkeypatch.setattr(wa.httpx, "get", _Red().get)
    if webhook_previo:
        _guardar_estado(db_session, "wamid.previo", "sent")
    contador = iter(range(1, 10))

    def _post(url, headers=None, json=None, timeout=None):
        if not aceptar_envio:
            return _resp(400, {"error": {"code": 132000, "message": "parámetros"}})
        return _resp(200, {"messages": [{"id": f"wamid.D{next(contador)}"}]})

    monkeypatch.setattr(wa.httpx, "post", _post)
    for mid, estados in estados_por_mensaje.items():
        for est, cod, tit in estados:
            _guardar_estado(db_session, mid, est, cod, tit)
    return wa.diagnosticar_aviso_reserva()


def test_diagnostico_completo_con_entregas_fallo_y_pendientes(config, bd_de_pruebas, db_session, monkeypatch):
    r = _diagnostico_completo(
        monkeypatch, db_session, webhook_previo=True,
        estados_por_mensaje={"wamid.D1": [("delivered", None, None)], "wamid.D2": [("failed", "131030", "x")]},
    )
    pasos = {p["clave"]: p for p in r["pasos"]}
    assert pasos["entrega_2233"]["ok"] and "llegó al teléfono" in pasos["entrega_2233"]["detalle"]
    assert not pasos["entrega_5566"]["ok"] and "lista de destinatarios" in pasos["entrega_5566"]["detalle"]
    assert pasos["webhook"]["ok"] and pasos["destinos"]["ok"] and pasos["envio_2233"]["ok"]
    assert r["ok"] is False  # una entrega falló


def test_diagnostico_sin_webhook_con_estado_sent_y_sin_estado(config, bd_de_pruebas, db_session, monkeypatch):
    r = _diagnostico_completo(monkeypatch, db_session, webhook_previo=False, estados_por_mensaje={})
    pasos = {p["clave"]: p for p in r["pasos"]}
    assert not pasos["webhook"]["ok"] and "nunca ha enviado" in pasos["webhook"]["detalle"]
    assert "Conecta el webhook" in pasos["entrega_2233"]["detalle"]

    # con webhook activo: un mensaje solo en «sent» y otro sin ningún estado
    r2 = _diagnostico_completo(monkeypatch, db_session, webhook_previo=True, estados_por_mensaje={"wamid.D1": [("sent", None, None)]})
    p2 = {p["clave"]: p for p in r2["pasos"]}
    assert "aún no confirma la entrega" in p2["entrega_2233"]["detalle"]
    assert "vuelve a pulsar" in p2["entrega_5566"]["detalle"]


def test_diagnostico_con_envio_rechazado_y_sin_destinatarios(config, bd_de_pruebas, db_session, monkeypatch):
    r = _diagnostico_completo(monkeypatch, db_session, webhook_previo=True, estados_por_mensaje={}, aceptar_envio=False)
    pasos = {p["clave"]: p for p in r["pasos"]}
    assert not pasos["envio_2233"]["ok"] and "132000" in pasos["envio_2233"]["detalle"]
    assert not any(k.startswith("entrega_") for k in pasos)

    monkeypatch.setattr(config, "whatsapp_notify_to", "123")
    monkeypatch.setattr(wa, "destinatarios", lambda v: [])
    monkeypatch.setattr(wa, "_faltantes_aviso", lambda: [])
    r = wa.diagnosticar_aviso_reserva()
    assert not {p["clave"]: p for p in r["pasos"]}["destinos"]["ok"]


def test_diagnostico_en_entorno_serverless(config, bd_de_pruebas, monkeypatch):
    monkeypatch.setenv("NOTIFICACIONES_EN_LINEA", "true")
    monkeypatch.setattr(wa.httpx, "get", _Red(error=httpx.ConnectError("x")).get)
    pasos = {p["clave"]: p for p in wa.diagnosticar_aviso_reserva()["pasos"]}
    assert "Serverless" in pasos["entorno"]["detalle"]


def test_sesion_bd_usa_la_fabrica_de_sesiones_de_la_app(monkeypatch):
    from app.infrastructure.database import session as modulo_sesion
    from tests.conftest import _TestingSessionLocal

    monkeypatch.setattr(modulo_sesion, "SessionLocal", _TestingSessionLocal)
    with wa._sesion_bd() as db:
        assert db.get_bind() is _TestingSessionLocal.kw["bind"]
