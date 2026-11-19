"""Panel del administrador y utilidades: configuración del bot, pruebas de IA/WhatsApp, límites del chat público,
conversaciones, inventario con filtros, pases públicos, notificaciones y tareas en segundo plano."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.api.v1 import chat_router
from app.application import bot_config, chat_service, notificacion_service
from app.application.ia_client import ClienteIA, IANoDisponible
from app.application.qr_format import MAX_LONGITUD, leer_qr
from app.core import tareas
from app.core.exceptions import ValidationError
from app.infrastructure.models.chat_model import ChatMensajeModel, ChatSesionModel
from app.infrastructure.models.invitado_model import InvitadoModel

API = "/api/v1"


# ------------------------------------------------------------------ bot: estado y pruebas
def _estado(client, auth):
    return client.get(f"{API}/bot/estado", headers=auth).json()


def test_estado_del_bot_describe_los_proveedores_de_ia(client, auth, monkeypatch):
    monkeypatch.setattr(ClienteIA, "configurada", property(lambda s: True))

    def con(claves, groq):
        monkeypatch.setattr(ClienteIA, "claves_configuradas", property(lambda s: claves))
        monkeypatch.setattr(ClienteIA, "con_groq", property(lambda s: groq))
        e = _estado(client, auth)
        ia = next(p for p in e["checklist"] if p["clave"] == "ia")
        return e["ia_proveedor"], ia["detalle"], ia["ok"]

    prov, detalle, ok = con(1, True)
    assert prov == "Google Gemini + Groq (respaldo)" and "Gemini con 1 clave + Groq como respaldo" in detalle and ok
    prov, detalle, _ = con(2, False)
    assert prov == "Google Gemini" and "Gemini con 2 claves" in detalle
    prov, detalle, _ = con(0, True)
    assert prov == "Groq" and detalle.endswith("Groq; el asistente entiende lenguaje natural.")


def test_probar_conexion_ia_sin_clave_con_exito_y_con_fallo(client, auth, monkeypatch):
    sin = client.post(f"{API}/bot/ia/probar", headers=auth).json()
    assert sin["ok"] is False and "GEMINI_API_KEY" in sin["detalle"]

    monkeypatch.setattr(ClienteIA, "configurada", property(lambda s: True))
    monkeypatch.setattr(ClienteIA, "modelo", property(lambda s: "modelo-falso"))
    monkeypatch.setattr(ClienteIA, "json", lambda self, **kw: {"ok": True})
    ok = client.post(f"{API}/bot/ia/probar", headers=auth).json()
    assert ok["ok"] is True and "modelo-falso" in ok["detalle"] and ok["milisegundos"] >= 0

    def _falla(self, **kw):
        raise IANoDisponible("cuota agotada")

    monkeypatch.setattr(ClienteIA, "json", _falla)
    mal = client.post(f"{API}/bot/ia/probar", headers=auth).json()
    assert mal["ok"] is False and mal["detalle"] == "cuota agotada"


def test_prueba_de_whatsapp_con_plantilla_y_con_texto(client, auth, monkeypatch):
    llamadas = []
    monkeypatch.setattr("app.api.v1.bot_router.enviar_aviso_prueba", lambda tel: llamadas.append(("plantilla", tel)) or ("enviada", None))
    r = client.post(f"{API}/bot/whatsapp/prueba", json={"telefono": "+57 300 123 4567"}, headers=auth).json()
    assert r["ok"] and "…4567" in r["detalle"] and llamadas == [("plantilla", "573001234567")]

    monkeypatch.setattr("app.api.v1.bot_router.enviar_aviso_prueba", lambda tel: ("fallida", None))
    assert client.post(f"{API}/bot/whatsapp/prueba", json={"telefono": "3001234567"}, headers=auth).json() == {"ok": False, "detalle": "No se pudo enviar el aviso de prueba.", "milisegundos": None}

    monkeypatch.setattr("app.api.v1.bot_router.responder_mensaje_bot_whatsapp", lambda tel, txt: ("respondido", None))
    assert client.post(f"{API}/bot/whatsapp/prueba", json={"telefono": "3001234567", "texto": "hola"}, headers=auth).json()["ok"] is True
    monkeypatch.setattr("app.api.v1.bot_router.responder_mensaje_bot_whatsapp", lambda tel, txt: ("fallida", "Meta rechazó"))
    assert client.post(f"{API}/bot/whatsapp/prueba", json={"telefono": "3001234567", "texto": "hola"}, headers=auth).json()["detalle"] == "Meta rechazó"
    monkeypatch.setattr("app.api.v1.bot_router.responder_mensaje_bot_whatsapp", lambda tel, txt: ("fallida", None))
    assert client.post(f"{API}/bot/whatsapp/prueba", json={"telefono": "3001234567", "texto": "hola"}, headers=auth).json()["detalle"] == "No se pudo enviar el mensaje."
    assert client.post(f"{API}/bot/whatsapp/prueba", json={"telefono": "abc"}, headers=auth).status_code == 422


def test_configuracion_del_bot_se_valida_y_se_actualiza(client, auth, db_session):
    base = client.get(f"{API}/bot/configuracion", headers=auth).json()
    assert base["valores"]["nombre_bot"] == "Medi" and base["campos"]
    ok = client.put(f"{API}/bot/configuracion", json={"nombre_bot": "Lola", "bot_activo": False, "edad_minima": 21, "hora_limite_defecto": "22:00"}, headers=auth)
    assert ok.status_code == 200 and ok.json()["valores"]["bot_activo"] == "false" and ok.json()["valores"]["edad_minima"] == "21"
    # actualizar una clave ya guardada modifica la fila existente (no crea otra)
    assert client.put(f"{API}/bot/configuracion", json={"nombre_bot": "Rosa"}, headers=auth).json()["valores"]["nombre_bot"] == "Rosa"
    assert bot_config.obtener_config(db_session)["nombre_bot"] == "Rosa"

    for cambios in ({"inventada": "x"}, {"bot_activo": "quizás"}, {"edad_minima": "abc"}, {"edad_minima": 0}, {"hora_limite_defecto": "25:00"}, {"saludo": "x" * 601}):
        r = client.put(f"{API}/bot/configuracion", json=cambios, headers=auth)
        assert r.status_code == 422, cambios
    with pytest.raises(ValidationError):
        bot_config.actualizar_config(db_session, {"escalar_negativos": "tal vez"})
    # el asistente en pausa responde sin ejecutar el flujo
    pausado = client.post(f"{API}/chat/mensajes", json={"texto": "hola"})
    assert pausado.status_code == 200 and "pausa" in pausado.json()["mensajes"][0]["texto"]


# ------------------------------------------------------------------ chat público: límites
def test_limite_de_frecuencia_por_ip_y_limpieza_del_historial(client, monkeypatch):
    monkeypatch.setattr(chat_router, "_limitador", chat_router._LimitadorFrecuencia(2))
    assert client.post(f"{API}/chat/mensajes", json={"texto": "hola"}).status_code == 200
    assert client.post(f"{API}/chat/mensajes", json={"texto": "hola"}).status_code == 200
    r = client.post(f"{API}/chat/mensajes", json={"texto": "hola"})
    assert r.status_code == 429 and "muy rápido" in r.json()["detail"]

    reloj = iter([0.0, 10.0, 100.0])
    monkeypatch.setattr(chat_router.time, "monotonic", lambda: next(reloj))
    lim = chat_router._LimitadorFrecuencia(1, ventana=60.0)
    assert lim.permitir("a") is True      # t=0
    assert lim.permitir("a") is False     # t=10: ya llegó al máximo dentro de la ventana
    assert lim.permitir("a") is True      # t=100: la visita antigua expiró y se descarta
    monkeypatch.undo()
    grande = chat_router._LimitadorFrecuencia(5)
    for i in range(5001):
        grande.permitir(f"ip{i}")
    assert grande.permitir("nueva") is True and len(grande._visitas) <= 5002  # se reinicia en vez de crecer sin límite


def test_limite_de_mensajes_por_conversacion(client, monkeypatch):
    monkeypatch.setattr(chat_router, "_limitador", chat_router._LimitadorFrecuencia(1000))
    monkeypatch.setattr(chat_router, "LIMITE_MENSAJES_POR_SESION", 2)
    sesion = client.post(f"{API}/chat/mensajes", json={"texto": "hola"}).json()["sesion_id"]
    assert client.post(f"{API}/chat/mensajes", json={"texto": "¿horario?", "sesion_id": sesion}).status_code == 200
    r = client.post(f"{API}/chat/mensajes", json={"texto": "otra", "sesion_id": sesion})
    assert r.status_code == 429 and "límite de mensajes" in r.json()["detail"]


# ------------------------------------------------------------------ servicio de conversaciones
def test_purga_de_conversaciones_antiguas_y_estado_corrupto(db_session):
    vieja = chat_service._nueva_sesion(db_session, "web", None, {"paso": "libre"})
    reciente = chat_service._nueva_sesion(db_session, "web", None, {"paso": "libre"})
    db_session.add(ChatMensajeModel(sesion_id=vieja.id, autor="usuario", texto="hola"))
    vieja.actualizada_en = datetime.now(timezone.utc) - timedelta(days=chat_service.RETENCION_DIAS + 5)
    db_session.commit()
    id_vieja, id_reciente = vieja.id, reciente.id
    assert chat_service.purgar_antiguas(db_session) == 1
    assert chat_service.purgar_antiguas(db_session) == 0
    assert db_session.get(ChatSesionModel, id_vieja) is None and db_session.get(ChatSesionModel, id_reciente) is not None
    assert db_session.execute(select(ChatMensajeModel)).scalars().all() == []

    reciente.estado_dialogo = "{no es json"
    assert chat_service.estado_de(reciente) == {}
    reciente.estado_dialogo = "[1, 2]"
    assert chat_service.estado_de(reciente) == {}
    reciente.estado_dialogo = None
    assert chat_service.estado_de(reciente) == {}


def test_sesion_de_whatsapp_se_reutiliza_dentro_de_la_ventana_y_se_renueva_fuera(db_session):
    a = chat_service.obtener_sesion_whatsapp(db_session, "573001234567")
    assert chat_service.obtener_sesion_whatsapp(db_session, "573001234567").id == a.id
    assert a.contacto_hash == chat_service.hash_contacto("573001234567") and "573001234567" not in a.contacto_hash
    a.actualizada_en = datetime.now(timezone.utc) - chat_service.VENTANA_WHATSAPP - timedelta(minutes=1)
    db_session.commit()
    assert chat_service.obtener_sesion_whatsapp(db_session, "573001234567").id != a.id


# ------------------------------------------------------------------ conversaciones (panel de sentimientos)
def test_panel_de_conversaciones_filtros_detalle_y_resolucion(client, auth, db_session, crear_usuario):
    web = client.post(f"{API}/chat/mensajes", json={"texto": "Me robaron el celular, una estafa"}).json()["sesion_id"]
    client.post(f"{API}/chat/mensajes", json={"texto": "hola"})  # otra sesión sin escalar
    wa = chat_service.obtener_sesion_whatsapp(db_session, "573009990000")
    wa.escalada = True
    db_session.commit()

    todas = client.get(f"{API}/sentimientos/conversaciones", headers=auth).json()
    assert len(todas) == 3
    assert {c["id"] for c in client.get(f"{API}/sentimientos/conversaciones?estado=escaladas", headers=auth).json()} == {web, wa.id}
    assert [c["id"] for c in client.get(f"{API}/sentimientos/conversaciones?canal=whatsapp", headers=auth).json()] == [wa.id]
    assert len(client.get(f"{API}/sentimientos/conversaciones?estado=abiertas&canal=web", headers=auth).json()) == 1

    detalle = client.get(f"{API}/sentimientos/conversaciones/{web}", headers=auth).json()
    assert detalle["escalada"] and [m["autor"] for m in detalle["mensajes"]][:2] == ["usuario", "bot"] and detalle["mensajes"][0]["aspectos"] is not None
    assert client.get(f"{API}/sentimientos/conversaciones/nada", headers=auth).status_code == 404
    res = client.post(f"{API}/sentimientos/conversaciones/{web}/resolver", headers=auth).json()
    assert res["escalada_resuelta"] is True
    assert len(client.get(f"{API}/sentimientos/conversaciones?estado=abiertas&canal=web", headers=auth).json()) == 0
    assert client.post(f"{API}/sentimientos/conversaciones/nada/resolver", headers=auth).status_code == 404
    assert client.get(f"{API}/sentimientos/conversaciones", headers=crear_usuario("p@nightlife.io", "Promotor")["headers"]).status_code == 403
    panel = client.get(f"{API}/sentimientos/panel?dias=7", headers=auth)
    assert panel.status_code == 200


def test_analizar_sentimiento_con_y_sin_ia(client, auth, monkeypatch):
    assert client.post(f"{API}/sentimientos/analizar", json={"texto": "  ab "}, headers=auth).status_code == 422
    base = client.post(f"{API}/sentimientos/analizar", json={"texto": "La música estuvo excelente"}, headers=auth).json()
    assert base["etiqueta"] == "positivo"
    sin_ia = client.post(f"{API}/sentimientos/analizar", json={"texto": "La música estuvo excelente", "usar_ia": True}, headers=auth).json()
    assert "aviso_ia" in sin_ia  # la IA no está disponible: se avisa y se conserva el análisis local

    from app.application.chat_nlu import NLU

    monkeypatch.setattr("app.api.v1.sentimientos_router.nlu_ia", lambda *a, **k: NLU(sentimiento={"etiqueta": "negativo", "urgente": False, "motivo_urgencia": None}, ia=True))
    monkeypatch.setattr(ClienteIA, "modelo", property(lambda s: "modelo-falso"))
    con_ia = client.post(f"{API}/sentimientos/analizar", json={"texto": "La música estuvo excelente", "usar_ia": True}, headers=auth).json()
    assert con_ia["etiqueta"] == "negativo" and "modelo-falso" in con_ia["metodo"]


# ------------------------------------------------------------------ inventario: filtros y movimientos
def _item(client, auth, nombre, categoria, cantidad, minimo=5):
    r = client.post(f"{API}/inventario", json={"nombre": nombre, "categoria": categoria, "cantidad": cantidad, "unidad": "und", "stock_minimo": minimo}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def test_inventario_filtros_y_movimientos(client, auth, crear_evento, monkeypatch):
    monkeypatch.setattr("app.api.v1.inventario_router.notificar_stock_bajo", lambda d: None)
    ron = _item(client, auth, "Ron Medellín", "Licores", 10)
    agua = _item(client, auth, "Agua", "Bebidas", 2)  # bajo el mínimo
    hielo = _item(client, auth, "Hielo", "Bebidas", 0)  # agotado
    nombres = lambda params: sorted(i["nombre"] for i in client.get(f"{API}/inventario{params}", headers=auth).json())
    assert nombres("?buscar=ron") == ["Ron Medellín"]
    assert nombres("?buscar=%20%20") == ["Agua", "Hielo", "Ron Medellín"]
    assert nombres("?categoria=Bebidas") == ["Agua", "Hielo"]
    assert nombres("?categoria=Bebidas&estado=bajo") == ["Agua"]
    assert nombres("?estado=agotado") == ["Hielo"]
    assert nombres("?estado=ok") == ["Ron Medellín"]

    evento = crear_evento()
    mov = lambda item, **cuerpo: client.post(f"{API}/inventario/{item['id']}/movimientos", json=cuerpo, headers=auth)
    assert mov(ron, tipo="consumo", cantidad=3, evento_id=evento["id"], motivo="  Barra  ").status_code == 201
    assert mov(ron, tipo="entrada", cantidad=5).status_code == 201
    assert mov(ron, tipo="ajuste", cantidad=4).json()["item"]["cantidad"] in (4, "4.00", 4.0)
    assert mov(ron, tipo="salida", cantidad=100).status_code == 409  # no se puede sacar más de lo que hay
    assert mov(ron, tipo="entrada", cantidad=0).status_code == 422
    assert mov(ron, tipo="consumo", cantidad=1, evento_id=9999).status_code == 404
    assert client.post(f"{API}/inventario/9999/movimientos", json={"tipo": "entrada", "cantidad": 1}, headers=auth).status_code == 404

    todos = client.get(f"{API}/inventario/movimientos", headers=auth).json()
    assert todos[0]["item_nombre"] == "Ron Medellín" and {"consumo", "entrada", "ajuste"} <= {m["tipo"] for m in todos}
    assert {m["tipo"] for m in client.get(f"{API}/inventario/movimientos?tipo=consumo", headers=auth).json()} == {"consumo"}
    assert len(client.get(f"{API}/inventario/movimientos?evento_id={evento['id']}", headers=auth).json()) == 1
    assert len(client.get(f"{API}/inventario/movimientos?limite=1", headers=auth).json()) == 1
    historial = client.get(f"{API}/inventario/{ron['id']}/movimientos", headers=auth).json()
    assert [m["tipo"] for m in historial][:3] == ["ajuste", "entrada", "consumo"]  # el más reciente primero
    consumo = client.get(f"{API}/inventario/eventos/{evento['id']}/consumo", headers=auth).json()
    assert [(c["item_id"], Decimal(str(c["cantidad"]))) for c in consumo] == [(ron["id"], Decimal("3"))]
    resumen = client.get(f"{API}/inventario/resumen", headers=auth).json()
    assert resumen["productos"] == 3
    assert client.get(f"{API}/inventario/exportar.csv", headers=auth).text.count("\n") >= 3
    assert client.delete(f"{API}/inventario/{hielo['id']}", headers=auth).status_code == 204
    assert client.delete(f"{API}/inventario/{agua['id']}", headers=auth).status_code == 204
    assert client.delete(f"{API}/inventario/{agua['id']}", headers=auth).status_code == 404


# ------------------------------------------------------------------ pases públicos
def _pase_garantizado(client, auth, crear_evento):
    evento = crear_evento(tematica="Retro")
    r = client.post(f"{API}/reservas", json={"evento_id": evento["id"], "nombre_cliente": "Ana Torres", "telefono": "3001234567", "tipo": "palco", "asistentes": 2})
    rid = r.json()["id"]
    client.patch(f"{API}/reservas/{rid}/estado", json={"estado": "confirmada", "ubicacion_asignada": "Palco; 2, norte", "hora_limite": "23:30"}, headers=auth)
    return evento, client.get(f"{API}/reservas/{rid}/pases", headers=auth).json()[0]


def test_pase_publico_calendario_e_imagen_qr(client, auth, crear_evento, monkeypatch):
    monkeypatch.setattr("app.api.v1.reservas_router.notificar_confirmacion_reserva", lambda d: ("enviada", None, "w"))
    evento, pase = _pase_garantizado(client, auth, crear_evento)
    codigo = pase["qr_code"]
    publico = client.get(f"{API}/pases/{codigo}").json()
    assert publico["valido"] is True and publico["reserva"]["ubicacion_asignada"] == "Palco; 2, norte" and publico["evento_tematica"] == "Retro"
    ics = client.get(f"{API}/pases/{codigo}/calendario.ics")
    assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VEVENT" in ics.text and "Ubicación: Palco\\; 2\\, norte." in ics.text and "Llega antes de las 23:30." in ics.text and "Reserva garantizada MC-" in ics.text
    assert client.get(f"{API}/pases/{codigo}/qr.png").headers["content-type"] == "image/png"
    assert "svg" in client.get(f"{API}/pases/{codigo}/qr.svg").headers["content-type"]
    assert client.get(f"{API}/pases/{codigo}/qr.gif").status_code in (404, 422)
    # evento cerrado: el pase deja de ser válido
    client.put(f"{API}/eventos/{evento['id']}", json={"estado": "cerrado"}, headers=auth)
    assert client.get(f"{API}/pases/{codigo}").json()["valido"] is False
    assert client.get(f"{API}/pases/NLD-1-XXXXXXXXXXXXXXXX").status_code == 404
    assert client.get(f"{API}/pases/basura/calendario.ics").status_code == 404


def test_pase_cuyo_evento_ya_no_existe_es_404(client, db_session):
    db_session.add(InvitadoModel(evento_id=777, promotor_id=1, nombre="x", qr_code="NLD-777-AAAAAAAAAAAAAAAA", estado="pendiente"))
    db_session.commit()
    assert client.get(f"{API}/pases/NLD-777-AAAAAAAAAAAAAAAA").status_code == 404


def test_pase_manual_sin_reserva_en_calendario(client, auth, crear_evento, crear_usuario):
    evento = crear_evento()
    pro = crear_usuario("pro@nightlife.io", "Promotor")
    inv = client.post(f"{API}/invitados", json={"nombre": "Luis", "evento_id": evento["id"], "promotor_id": pro["id"]}, headers=auth).json()
    ics = client.get(f"{API}/pases/{inv['qr_code']}/calendario.ics").text
    assert "Pase para Luis" in ics and "Reserva garantizada" not in ics
    assert client.get(f"{API}/pases/{inv['qr_code']}").json()["reserva"] is None


# ------------------------------------------------------------------ QR: lectura y render
def test_leer_qr_rechaza_tipos_y_longitudes_invalidas():
    with pytest.raises(ValueError, match="debe ser texto"):
        leer_qr(None)
    with pytest.raises(ValueError, match="demasiado largo"):
        leer_qr("a" * (MAX_LONGITUD + 1))
    with pytest.raises(ValueError, match="no reconocido"):
        leer_qr("hola mundo")


def test_leer_qr_ignora_base64_que_no_decodifica_a_un_pase():
    # base64 válido de «hola mundo, esto no es un pase» y base64 que no es UTF-8: ninguno contiene un código NLD
    import base64

    with pytest.raises(ValueError):
        leer_qr(base64.urlsafe_b64encode(b"hola mundo, esto no es un pase").decode())
    assert pytest.raises(ValueError, leer_qr, base64.urlsafe_b64encode(b"\xff\xfe\xfd" * 12).decode())


def test_render_qr_formatos():
    from app.application.qr_render import renderizar_qr

    datos, tipo = renderizar_qr("NLD-1-AAAAAAAAAAAAAAAA", "png")
    assert tipo == "image/png" and datos[1:4] == b"PNG"
    datos, tipo = renderizar_qr("NLD-1-AAAAAAAAAAAAAAAA")
    assert tipo == "image/svg+xml" and b"<svg" in datos
    with pytest.raises(ValueError, match="no soportado"):
        renderizar_qr("x", "gif")


# ------------------------------------------------------------------ notificaciones y tareas
def test_notificacion_con_nivel_invalido_y_marcar_leida_inexistente(db_session, client, auth):
    n = notificacion_service.notificar(db_session, tipo="x", titulo="t", mensaje="m", nivel="rarísimo")
    assert n.nivel == "info"
    from app.domain.entities.usuario import Usuario
    from app.domain.enums import RolUsuario

    admin = Usuario(id=1, nombre="a", email="a@a.io", password_hash="h", rol=RolUsuario.ADMINISTRADOR)
    assert notificacion_service.marcar_leida(db_session, admin, 99999) is False


def test_es_serverless_segun_variables_de_entorno(monkeypatch):
    for k in ("NOTIFICACIONES_EN_LINEA", "VERCEL", "AWS_LAMBDA_FUNCTION_NAME"):
        monkeypatch.delenv(k, raising=False)
    assert tareas.es_serverless() is False
    monkeypatch.setenv("VERCEL", "1")
    assert tareas.es_serverless() is True
    monkeypatch.setenv("NOTIFICACIONES_EN_LINEA", "no")  # el forzado manda sobre la detección
    assert tareas.es_serverless() is False
    monkeypatch.setenv("NOTIFICACIONES_EN_LINEA", "sí")
    assert tareas.es_serverless() is True


def test_lanzar_en_segundo_plano_o_en_linea_sin_romper_la_peticion(monkeypatch):
    from fastapi import BackgroundTasks

    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.setenv("NOTIFICACIONES_EN_LINEA", "false")
    fondo = BackgroundTasks()
    llamadas = []
    tareas.lanzar(fondo, lambda x: llamadas.append(x), 1)
    assert llamadas == [] and len(fondo.tasks) == 1  # se programa, no se ejecuta aún

    monkeypatch.setenv("NOTIFICACIONES_EN_LINEA", "true")
    tareas.lanzar(fondo, lambda x: llamadas.append(x), 2)
    assert llamadas == [2] and len(fondo.tasks) == 1

    def _rota():
        raise RuntimeError("Meta caído")

    tareas.lanzar(fondo, _rota)  # una tarea que falla en línea se registra pero no propaga el error
