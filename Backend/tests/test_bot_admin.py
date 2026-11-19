import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models.chat_model import ChatMensajeModel, ChatSesionModel
from app.infrastructure.models.reserva_model import ReservaModel


def _chat(client: TestClient, texto: str, sesion_id: str | None = None) -> dict:
    cuerpo = {"texto": texto, **({"sesion_id": sesion_id} if sesion_id else {})}
    respuesta = client.post("/api/v1/chat/mensajes", json=cuerpo)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_estado_checklist_y_permisos(client: TestClient, auth, crear_usuario) -> None:
    estado = client.get("/api/v1/bot/estado", headers=auth).json()
    assert estado["ia_configurada"] is False and estado["ia_activa"] is False
    assert estado["webhook_ruta"] == "/webhooks/whatsapp"
    claves = {p["clave"] for p in estado["checklist"]}
    assert {"chat", "ia", "wa_credenciales", "wa_webhook", "wa_confirmacion", "wa_inventario"} <= claves
    # Nunca se exponen los valores de los secretos (solo si están configurados o no).
    from app.core.config import get_settings

    ajustes = get_settings()
    texto = json.dumps(estado)
    for secreto in (ajustes.whatsapp_access_token, ajustes.whatsapp_app_secret, ajustes.whatsapp_webhook_verify_token, ajustes.gemini_api_key):
        assert not secreto or secreto not in texto

    puerta = crear_usuario("puerta@nightlife.io", "Puerta")
    assert client.get("/api/v1/bot/estado", headers=puerta["headers"]).status_code == 403
    assert client.get("/api/v1/bot/estado").status_code == 401


def test_configuracion_se_guarda_valida_y_gobierna_al_bot(client: TestClient, auth) -> None:
    actual = client.get("/api/v1/bot/configuracion", headers=auth).json()
    assert actual["valores"]["nombre_bot"] == "Medi" and len(actual["campos"]) >= 10

    nueva = client.put(
        "/api/v1/bot/configuracion",
        json={"horario": "Viernes y sábado, 9 p. m. a 4 a. m.", "edad_minima": 21, "escalar_negativos": False},
        headers=auth,
    )
    assert nueva.status_code == 200 and nueva.json()["valores"]["edad_minima"] == "21"
    respuesta = _chat(client, "¿a qué hora abren?")
    assert "Viernes y sábado" in respuesta["mensajes"][0]["texto"]

    # Con la escalación apagada una queja se registra pero no avisa al equipo.
    queja = _chat(client, "El servicio fue horrible, qué mamera")
    assert queja["escalada"] is False

    assert client.put("/api/v1/bot/configuracion", json={"hora_limite_defecto": "25:00"}, headers=auth).status_code == 422
    assert client.put("/api/v1/bot/configuracion", json={"inventada": "x"}, headers=auth).status_code == 422
    assert client.put("/api/v1/bot/configuracion", json={"edad_minima": "abc"}, headers=auth).status_code == 422


def test_probador_no_crea_reservas_ni_notificaciones(client: TestClient, auth, crear_evento, db_session: Session) -> None:
    crear_evento()
    estado = None
    for texto in ("quiero una mesa para 2", "Pedro Pérez", "3009998877", "no", "sí"):
        respuesta = client.post("/api/v1/bot/probar", json={"texto": texto, "estado": estado}, headers=auth)
        assert respuesta.status_code == 200, respuesta.text
        estado = respuesta.json()["estado"]
    assert respuesta.json()["respuesta"]["reserva"]["simulada"] is True
    assert db_session.execute(select(ReservaModel)).scalars().all() == []
    assert client.post("/api/v1/bot/probar", json={}, headers=auth).status_code == 422


def test_ia_sin_clave_informa_que_falta_configurarla(client: TestClient, auth) -> None:
    resultado = client.post("/api/v1/bot/ia/probar", headers=auth).json()
    assert resultado["ok"] is False and "GEMINI_API_KEY" in resultado["detalle"]
    analisis = client.post("/api/v1/sentimientos/analizar", json={"texto": "La atención fue excelente", "usar_ia": True}, headers=auth).json()
    assert analisis["etiqueta"] == "positivo" and "aviso_ia" in analisis  # cae al motor local


def test_prueba_de_whatsapp_usa_el_envio_real_solo_cuando_el_admin_lo_pide(client: TestClient, auth, monkeypatch) -> None:
    textos, plantillas = [], []
    monkeypatch.setattr("app.api.v1.bot_router.responder_mensaje_bot_whatsapp", lambda tel, txt: textos.append((tel, txt)) or ("respondido", None))
    monkeypatch.setattr("app.api.v1.bot_router.enviar_aviso_prueba", lambda tel: plantillas.append(tel) or ("enviada", None))
    ok = client.post("/api/v1/bot/whatsapp/prueba", json={"telefono": "+57 300 123 4567"}, headers=auth).json()
    assert ok["ok"] is True and plantillas == ["573001234567"] and not textos  # por defecto: plantilla aprobada (sin ventana de 24 h)
    libre = client.post("/api/v1/bot/whatsapp/prueba", json={"telefono": "573001234567", "texto": "hola"}, headers=auth).json()
    assert libre["ok"] is True and textos == [("573001234567", "hola")]
    assert client.post("/api/v1/bot/whatsapp/prueba", json={"telefono": "abc"}, headers=auth).status_code == 422


def test_panel_de_sentimientos_y_conversaciones(client: TestClient, auth, db_session: Session) -> None:
    _chat(client, "Nos encantó la música, todo perfecto, gracias")
    queja = _chat(client, "El servicio fue pésimo y los tragos carísimos, qué desastre")
    _chat(client, "hola")

    panel = client.get("/api/v1/sentimientos/panel?dias=7", headers=auth).json()
    totales = panel["totales"]
    assert totales["mensajes"] == 3 and totales["positivo"] == 1 and totales["negativo"] == 1 and totales["neutral"] == 1
    assert totales["escaladas_abiertas"] == 1 and totales["sesiones"] == 3
    assert panel["por_canal"]["web"]["total"] == 3 and len(panel["tendencia"]) == 7
    aspectos = {a["aspecto"]: a for a in panel["aspectos"]}
    assert aspectos["servicio"]["negativo"] == 1 and aspectos["precio"]["negativo"] == 1
    assert aspectos["musica"]["positivo"] == 1
    assert {e["emocion"] for e in panel["emociones"]} >= {"alegria", "enojo"}

    escaladas = client.get("/api/v1/sentimientos/conversaciones?estado=abiertas", headers=auth).json()
    assert [c["id"] for c in escaladas] == [queja["sesion_id"]]
    detalle = client.get(f"/api/v1/sentimientos/conversaciones/{queja['sesion_id']}", headers=auth).json()
    assert detalle["mensajes"][0]["autor"] == "usuario" and "pésimo" in detalle["mensajes"][0]["texto"]
    assert detalle["mensajes"][0]["sentimiento"] == "negativo"

    resuelta = client.post(f"/api/v1/sentimientos/conversaciones/{queja['sesion_id']}/resolver", headers=auth)
    assert resuelta.json()["escalada_resuelta"] is True
    assert client.get("/api/v1/sentimientos/conversaciones?estado=abiertas", headers=auth).json() == []
    assert client.get("/api/v1/sentimientos/conversaciones/inexistente", headers=auth).status_code == 404


def _webhook(client: TestClient, monkeypatch, texto: str, remitente: str, mensaje_id: str, enviados: list) -> None:
    secreto = "secreto-de-prueba"
    ajustes = SimpleNamespace(whatsapp_app_secret=secreto, whatsapp_webhook_verify_token="v", whatsapp_reservation_page_url="")
    monkeypatch.setattr("app.api.v1.whatsapp_router.get_settings", lambda: ajustes)
    monkeypatch.setattr("app.api.v1.whatsapp_router.responder_mensaje_bot_whatsapp", lambda tel, txt: enviados.append(txt) or ("respondido", None))
    monkeypatch.setattr("app.api.v1.whatsapp_router.notificar_nueva_reserva", lambda datos: None)
    cuerpo = json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{"id": mensaje_id, "from": remitente, "type": "text", "text": {"body": texto}}]}}]}],
    }, separators=(",", ":")).encode()
    firma = "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    respuesta = client.post("/webhooks/whatsapp", content=cuerpo, headers={"Content-Type": "application/json", "X-Hub-Signature-256": firma})
    assert respuesta.status_code == 200


def test_whatsapp_conversa_reserva_y_no_guarda_texto_ni_telefono(
    client: TestClient, crear_evento, monkeypatch, db_session: Session
) -> None:
    crear_evento(nombre="Noche Retro")
    enviados: list[str] = []
    yo = "573001234567"
    for i, texto in enumerate(["hola", "quiero una mesa para 4", "Camila Ríos", "no", "sí"], 1):
        _webhook(client, monkeypatch, texto, yo, f"wamid.{i}", enviados)

    assert "Responde con el número" in enviados[0]
    assert "contacto +573001234567" in enviados[3]  # el número del chat se usa como contacto
    assert "Registré tu solicitud #" in enviados[4] and "reserva=" in enviados[4]

    reserva = db_session.execute(select(ReservaModel)).scalar_one()
    assert (reserva.nombre_cliente, reserva.asistentes, reserva.telefono) == ("Camila Ríos", 4, "+573001234567")

    sesion = db_session.execute(select(ChatSesionModel)).scalar_one()
    assert sesion.canal == "whatsapp" and sesion.contacto_hash == hashlib.sha256(yo.encode()).hexdigest()
    assert "573001234567" not in sesion.estado_dialogo.replace("+573001234567", "")  # ni en el estado
    mensajes = db_session.execute(select(ChatMensajeModel)).scalars().all()
    assert mensajes and all(m.texto is None for m in mensajes)  # solo metadata, sin texto


def test_whatsapp_consulta_y_cancela_por_numero(client: TestClient, crear_evento, monkeypatch, db_session: Session) -> None:
    crear_evento()
    enviados: list[str] = []
    yo = "573009998877"
    for i, texto in enumerate(["quiero una mesa para 2", "Pedro", "no", "sí"], 1):
        _webhook(client, monkeypatch, texto, yo, f"wamid.a{i}", enviados)
    _webhook(client, monkeypatch, "¿cómo va mi reserva?", yo, "wamid.b1", enviados)
    assert "pendiente" in enviados[-1]
    _webhook(client, monkeypatch, "quiero cancelar mi reserva", yo, "wamid.b2", enviados)
    assert "¿Seguro" in enviados[-1]
    _webhook(client, monkeypatch, "1", yo, "wamid.b3", enviados)  # opción 1: Sí, cancelar
    assert "cancelé" in enviados[-1]
    assert db_session.execute(select(ReservaModel)).scalar_one().estado == "cancelada"

    # Otro número no puede ver ni cancelar la reserva de alguien más.
    _webhook(client, monkeypatch, "¿cómo va mi reserva?", "573110000000", "wamid.c1", enviados)
    assert "No encuentro reservas" in enviados[-1]


def test_reintento_de_meta_no_duplica_reservas(client: TestClient, crear_evento, monkeypatch, db_session: Session) -> None:
    crear_evento()
    enviados: list[str] = []
    yo = "573001112233"
    for i, texto in enumerate(["quiero una mesa para 2", "Ana", "no"], 1):
        _webhook(client, monkeypatch, texto, yo, f"wamid.r{i}", enviados)
    _webhook(client, monkeypatch, "sí", yo, "wamid.r4", enviados)
    _webhook(client, monkeypatch, "sí", yo, "wamid.r4", enviados)  # misma entrega repetida
    assert len(db_session.execute(select(ReservaModel)).scalars().all()) == 1


# --- Diagnóstico de WhatsApp y ejecución de avisos en serverless ---------------------------------


def test_diagnostico_whatsapp_sin_configurar_explica_que_falta(client: TestClient, auth, monkeypatch) -> None:
    from app.core.config import get_settings

    ajustes = get_settings()
    for campo in ("whatsapp_access_token", "whatsapp_notify_to", "whatsapp_template_name", "whatsapp_phone_number_id"):
        monkeypatch.setattr(ajustes, campo, "")
    r = client.post("/api/v1/bot/whatsapp/diagnostico", headers=auth)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["ok"] is False and cuerpo["pasos"][0]["clave"] == "configuracion"
    assert "WHATSAPP_ACCESS_TOKEN" in cuerpo["pasos"][0]["detalle"] and "WHATSAPP_NOTIFY_TO" in cuerpo["pasos"][0]["detalle"]


def test_diagnostico_whatsapp_exige_administrador(client: TestClient) -> None:
    assert client.post("/api/v1/bot/whatsapp/diagnostico").status_code in (401, 403)


def test_en_serverless_los_avisos_se_ejecutan_antes_de_responder(monkeypatch):
    from fastapi import BackgroundTasks

    from app.core import tareas

    llamadas = []
    monkeypatch.setenv("VERCEL", "1")
    tarea = BackgroundTasks()
    tareas.lanzar(tarea, lambda x: llamadas.append(x), "ya")
    assert llamadas == ["ya"] and not tarea.tasks  # corrió en línea, no quedó pendiente

    monkeypatch.delenv("VERCEL")
    tareas.lanzar(tarea, lambda x: llamadas.append(x), "despues")
    assert llamadas == ["ya"] and len(tarea.tasks) == 1  # servidor normal: queda en segundo plano


def test_aviso_en_linea_que_falla_no_rompe_la_peticion(monkeypatch):
    from fastapi import BackgroundTasks

    from app.core import tareas

    monkeypatch.setenv("NOTIFICACIONES_EN_LINEA", "true")

    def falla():
        raise RuntimeError("Meta caído")

    tareas.lanzar(BackgroundTasks(), falla)  # no debe lanzar excepción


class _RespuestaMeta:
    def __init__(self, codigo: int, cuerpo: dict) -> None:
        self.status_code, self._cuerpo, self.text = codigo, cuerpo, json.dumps(cuerpo)

    def json(self) -> dict:
        return self._cuerpo

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


def _configurar_whatsapp(monkeypatch) -> None:
    from app.application import whatsapp_notification_service as servicio
    from app.core.config import get_settings
    from tests.conftest import _TestingSessionLocal

    monkeypatch.setattr(servicio, "_sesion_bd", lambda: _TestingSessionLocal())
    monkeypatch.setattr("time.sleep", lambda _s: None)

    ajustes = get_settings()
    for campo, valor in {
        "whatsapp_access_token": "EAA-token-de-prueba", "whatsapp_phone_number_id": "123",
        "whatsapp_template_name": "plantilla_x", "whatsapp_template_language": "es_CO", "whatsapp_notify_to": "573001112233",
    }.items():
        monkeypatch.setattr(ajustes, campo, valor)


def _meta(monkeypatch, *, token_valido: bool = True, envio: _RespuestaMeta) -> None:
    import httpx

    def get(url, **_kw):
        if "debug_token" in url:
            return _RespuestaMeta(200, {"data": {"is_valid": token_valido, "expires_at": 0, "scopes": ["whatsapp_business_messaging"]}})
        return _RespuestaMeta(200, {"display_phone_number": "+1 555", "verified_name": "Test", "quality_rating": "GREEN"})

    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: envio)


def test_diagnostico_exitoso_recorre_todos_los_pasos(client: TestClient, auth, monkeypatch) -> None:
    _configurar_whatsapp(monkeypatch)
    _meta(monkeypatch, envio=_RespuestaMeta(200, {"messages": [{"id": "wamid.X"}]}))
    cuerpo = client.post("/api/v1/bot/whatsapp/diagnostico", headers=auth).json()
    assert [p["clave"] for p in cuerpo["pasos"]] == ["configuracion", "entorno", "token", "numero", "webhook", "destinos", "envio_2233", "entrega_2233"]
    # Meta aceptó el mensaje, pero sin webhook conectado no se puede confirmar la entrega: el diagnóstico lo dice.
    assert cuerpo["ok"] is False
    por_clave = {p["clave"]: p for p in cuerpo["pasos"]}
    assert por_clave["envio_2233"]["ok"] is True and por_clave["entrega_2233"]["ok"] is False
    assert "webhook" in por_clave["entrega_2233"]["detalle"].lower()
    assert "EAA-token-de-prueba" not in json.dumps(cuerpo)  # jamás se devuelve el token


def test_diagnostico_token_vencido_se_detiene_y_lo_explica(client: TestClient, auth, monkeypatch) -> None:
    _configurar_whatsapp(monkeypatch)
    _meta(monkeypatch, token_valido=False, envio=_RespuestaMeta(200, {}))
    cuerpo = client.post("/api/v1/bot/whatsapp/diagnostico", headers=auth).json()
    assert cuerpo["ok"] is False and cuerpo["pasos"][-1]["clave"] == "token" and "venció" in cuerpo["pasos"][-1]["detalle"]


def test_diagnostico_plantilla_en_idioma_equivocado_muestra_el_error_de_meta(client: TestClient, auth, monkeypatch) -> None:
    _configurar_whatsapp(monkeypatch)
    error = {"error": {"code": 132001, "message": "Template name does not exist in the translation",
                       "error_data": {"details": "template name (plantilla_x) does not exist in es_CO"}}}
    _meta(monkeypatch, envio=_RespuestaMeta(404, error))
    cuerpo = client.post("/api/v1/bot/whatsapp/diagnostico", headers=auth).json()
    ultimo = cuerpo["pasos"][-1]
    assert cuerpo["ok"] is False and ultimo["clave"] == "envio_2233"
    assert "132001" in ultimo["detalle"] and "es_CO" in ultimo["detalle"]


def test_url_de_base_de_datos_de_neon_se_normaliza() -> None:
    from app.core.config import Settings

    for entrada in ("postgres://u:p@h/db?sslmode=require", "postgresql://u:p@h/db?sslmode=require"):
        assert Settings(database_url=entrada, _env_file=None).database_url == "postgresql+psycopg2://u:p@h/db?sslmode=require"
    ya_bien = "postgresql+psycopg2://u:p@h/db"
    assert Settings(database_url=ya_bien, _env_file=None).database_url == ya_bien
    assert Settings(database_url="sqlite:///./x.db", _env_file=None).database_url == "sqlite:///./x.db"


def test_si_hay_url_directa_de_neon_se_prefiere_a_la_del_pooler() -> None:
    from app.core.config import Settings

    ajustes = Settings(
        database_url="postgresql://u:p@host-pooler.neon.tech/db",
        database_url_unpooled="postgresql://u:p@host.neon.tech/db?sslmode=require", _env_file=None,
    )
    assert ajustes.database_url == "postgresql+psycopg2://u:p@host.neon.tech/db?sslmode=require"


def _estado_meta(db_factory, message_id: str, estado: str, codigo: str | None = None, titulo: str | None = None) -> None:
    from app.infrastructure.models.whatsapp_estado_model import WhatsAppEstadoModel

    with db_factory() as db:
        db.add(WhatsAppEstadoModel(message_id=message_id, estado=estado, codigo_error=codigo, titulo_error=titulo))
        db.commit()


def test_diagnostico_confirma_la_entrega_cuando_meta_la_reporta(client: TestClient, auth, monkeypatch) -> None:
    from tests.conftest import _TestingSessionLocal

    _configurar_whatsapp(monkeypatch)
    _meta(monkeypatch, envio=_RespuestaMeta(200, {"messages": [{"id": "wamid.OK"}]}))
    _estado_meta(_TestingSessionLocal, "evento-previo", "delivered")  # el webhook ya ha llegado alguna vez
    _estado_meta(_TestingSessionLocal, "wamid.OK", "delivered")
    cuerpo = client.post("/api/v1/bot/whatsapp/diagnostico", headers=auth).json()
    assert cuerpo["ok"] is True
    assert {p["clave"]: p["ok"] for p in cuerpo["pasos"]}["entrega_2233"] is True


def test_diagnostico_traduce_el_error_de_entrega_de_meta(client: TestClient, auth, monkeypatch) -> None:
    from tests.conftest import _TestingSessionLocal

    _configurar_whatsapp(monkeypatch)
    _meta(monkeypatch, envio=_RespuestaMeta(200, {"messages": [{"id": "wamid.NO"}]}))
    _estado_meta(_TestingSessionLocal, "wamid.NO", "failed", "131030", "Recipient phone number not in allowed list")
    cuerpo = client.post("/api/v1/bot/whatsapp/diagnostico", headers=auth).json()
    entrega = {p["clave"]: p for p in cuerpo["pasos"]}["entrega_2233"]
    assert cuerpo["ok"] is False and entrega["ok"] is False
    assert "131030" in entrega["detalle"] and "lista de destinatarios permitidos" in entrega["detalle"]


def test_el_webhook_guarda_los_estados_de_entrega_sin_el_telefono_completo(client: TestClient, monkeypatch) -> None:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.infrastructure.models.whatsapp_estado_model import WhatsAppEstadoModel
    from tests.conftest import _TestingSessionLocal

    ajustes = get_settings()
    monkeypatch.setattr(ajustes, "whatsapp_app_secret", "secreto-de-prueba")
    cuerpo = json.dumps({"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"statuses": [
        {"id": "wamid.ABC", "status": "failed", "recipient_id": "573009990001",
         "errors": [{"code": 131030, "title": "Recipient phone number not in allowed list"}]},
    ]}}]}]}).encode()
    firma = "sha256=" + hmac.new(b"secreto-de-prueba", cuerpo, hashlib.sha256).hexdigest()
    r = client.post("/webhooks/whatsapp", content=cuerpo, headers={"Content-Type": "application/json", "X-Hub-Signature-256": firma})
    assert r.status_code == 200
    with _TestingSessionLocal() as db:
        fila = db.execute(select(WhatsAppEstadoModel)).scalar_one()
    assert (fila.message_id, fila.estado, fila.codigo_error, fila.destinatario_fin) == ("wamid.ABC", "failed", "131030", "3342")


def test_destinatarios_acepta_varios_telefonos_sin_repetir() -> None:
    from app.application.whatsapp_notification_service import destinatarios

    assert destinatarios("573009990001, 573009990002;+57 300 999 0001") == ["573009990001", "573009990002"]
    assert destinatarios("") == [] and destinatarios("123") == []


def test_el_aviso_de_reserva_llega_a_todos_los_destinatarios(monkeypatch) -> None:
    from app.application import whatsapp_notification_service as servicio
    from app.core.config import get_settings

    ajustes = get_settings()
    for campo, valor in {"whatsapp_access_token": "t", "whatsapp_phone_number_id": "1", "whatsapp_template_name": "plantilla",
                         "whatsapp_notify_to": "573009990001, 573009990002"}.items():
        monkeypatch.setattr(ajustes, campo, valor)
    enviados = []

    def falso(nombre, idioma, destino, parametros, **_kw):
        enviados.append(destino)
        return ("fallida", "error simulado", None) if destino.endswith("3342") else ("enviada", None, "wamid.X")

    monkeypatch.setattr(servicio, "_enviar_plantilla", falso)
    servicio.notificar_nueva_reserva({"id": 1, "nombre_cliente": "Ana", "telefono": "1", "evento_nombre": "E", "tipo": "Mesa",
                                      "asistentes": 2, "promotor": "P", "notas": "n"})
    assert enviados == ["573009990001", "573009990002"]  # el fallo del primero no impide avisar al segundo
