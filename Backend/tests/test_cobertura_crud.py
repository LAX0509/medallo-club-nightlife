"""Pruebas de extremo a extremo (router + servicio + repositorio) de usuarios, eventos, invitados,
promotores, comisiones, alertas, accesos y dashboard, incluidas las ramas de error y de permisos."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token
from app.domain.entities.comision import Comision
from app.domain.entities.evento import Evento
from app.domain.enums import EstadoAlerta, NivelAlerta, TipoAlerta
from app.infrastructure.models.alerta_riesgo_model import AlertaRiesgoModel

API = "/api/v1"


@pytest.fixture
def promotor(crear_usuario):
    return crear_usuario("promo@nightlife.io", "Promotor")


@pytest.fixture
def puerta(crear_usuario):
    return crear_usuario("puerta@nightlife.io", "Puerta")


def _invitado(client, headers, evento_id, promotor_id, nombre="Invitado"):
    r = client.post(f"{API}/invitados", json={"nombre": nombre, "evento_id": evento_id, "promotor_id": promotor_id}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ usuarios / auth
def test_usuarios_crud_completo(client, auth, crear_usuario):
    u = crear_usuario("ana@nightlife.io", "Promotor")
    assert client.post(f"{API}/usuarios", json={"nombre": "Otra", "email": "ana@nightlife.io", "password": "Clave1234", "rol": "Promotor"}, headers=auth).status_code == 409
    crear_usuario("beto@nightlife.io", "Puerta")
    todos = client.get(f"{API}/usuarios", headers=auth).json()
    assert todos["total"] == 3
    solo = client.get(f"{API}/usuarios?rol=Puerta", headers=auth).json()
    assert solo["total"] == 1 and solo["items"][0]["email"] == "beto@nightlife.io"
    pag = client.get(f"{API}/usuarios?page=2&limit=2", headers=auth).json()
    assert len(pag["items"]) == 1
    assert client.get(f"{API}/usuarios/me", headers=u["headers"]).json()["email"] == "ana@nightlife.io"
    r = client.put(f"{API}/usuarios/{u['id']}", json={"nombre": "Ana Maria", "rol": "Puerta", "estado": False, "telefono": "3001234567"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Ana Maria" and r.json()["rol"] == "Puerta" and r.json()["estado"] is False and r.json()["telefono"] == "3001234567"
    # un usuario inactivo ya no puede entrar ni usar su token
    assert client.post(f"{API}/auth/login", json={"email": "ana@nightlife.io", "password": "Clave1234"}).status_code == 401
    assert client.get(f"{API}/usuarios/me", headers=u["headers"]).status_code == 401
    assert client.put(f"{API}/usuarios/9999", json={"nombre": "X"}, headers=auth).status_code == 404
    assert client.get(f"{API}/usuarios", headers=crear_usuario("c@nightlife.io", "Promotor")["headers"]).status_code == 403


def test_registro_publico_de_promotor(client):
    r = client.post(f"{API}/auth/register", json={"nombre": " Luis ", "email": "Luis@Mail.com", "password": "Clave1234", "telefono": " 300 "})
    assert r.status_code == 201
    assert r.json()["email"] == "luis@mail.com" and r.json()["nombre"] == "Luis"
    assert client.post(f"{API}/auth/login", json={"email": "luis@mail.com", "password": "Clave1234"}).json()["rol"] == "Promotor"
    assert client.post(f"{API}/auth/register", json={"nombre": "L", "email": "luis@mail.com", "password": "Clave1234"}).status_code == 409
    # contraseña sin número -> validación de esquema
    assert client.post(f"{API}/auth/register", json={"nombre": "L", "email": "x@mail.com", "password": "SoloLetras"}).status_code == 422


def test_creacion_de_usuario_exige_numero_en_password(client, auth):
    r = client.post(f"{API}/usuarios", json={"nombre": "L", "email": "y@mail.com", "password": "SoloLetras", "rol": "Puerta"}, headers=auth)
    assert r.status_code == 422


def test_login_y_tokens_invalidos(client, admin_token):
    assert client.post(f"{API}/auth/login", json={"email": "admin@nightlife.io", "password": "mala"}).status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": "nadie@nightlife.io", "password": "Admin1234"}).status_code == 401
    assert client.get(f"{API}/usuarios/me").status_code == 401
    assert client.get(f"{API}/usuarios/me", headers={"Authorization": "Bearer basura"}).status_code == 401
    ajustes = get_settings()
    sin_sub = jwt.encode({"x": 1}, ajustes.jwt_secret_key, algorithm=ajustes.jwt_algorithm)
    assert client.get(f"{API}/usuarios/me", headers={"Authorization": f"Bearer {sin_sub}"}).status_code == 401
    inexistente = create_access_token("99999")
    assert client.get(f"{API}/usuarios/me", headers={"Authorization": f"Bearer {inexistente}"}).status_code == 401
    assert decode_access_token(create_access_token("5", {"rol": "x"}))["rol"] == "x"
    with pytest.raises(ValueError):
        decode_access_token("no-es-jwt")


# ------------------------------------------------------------------ eventos
def test_eventos_listar_actualizar_eliminar(client, auth, crear_evento):
    e1 = crear_evento("Uno", dias=3, tematica="Retro")
    e2 = crear_evento("Dos", dias=9)
    lista = client.get(f"{API}/eventos", headers=auth).json()
    assert lista["total"] == 2 and lista["items"][0]["nombre"] == "Dos"  # más reciente primero
    assert len(client.get(f"{API}/eventos?page=2&limit=1", headers=auth).json()["items"]) == 1
    assert client.get(f"{API}/eventos/{e1['id']}", headers=auth).json()["tematica"] == "Retro"
    assert client.get(f"{API}/eventos/9999", headers=auth).status_code == 404

    nueva_fecha = (date.today() + timedelta(days=20)).isoformat()
    r = client.put(f"{API}/eventos/{e1['id']}", json={"nombre": "Uno B", "fecha": nueva_fecha, "aforo_maximo": 50, "tematica": "Neon", "estado": "en curso"}, headers=auth)
    assert r.status_code == 200
    assert (r.json()["nombre"], r.json()["fecha"], r.json()["aforo_maximo"], r.json()["tematica"], r.json()["estado"]) == ("Uno B", nueva_fecha, 50, "Neon", "en curso")
    # tematica null explícita la borra; omitirla la conserva
    assert client.put(f"{API}/eventos/{e1['id']}", json={"nombre": "Uno C"}, headers=auth).json()["tematica"] == "Neon"
    assert client.put(f"{API}/eventos/{e1['id']}", json={"tematica": None}, headers=auth).json()["tematica"] is None
    assert client.put(f"{API}/eventos/9999", json={"nombre": "x"}, headers=auth).status_code == 404

    assert client.delete(f"{API}/eventos/{e2['id']}", headers=auth).status_code == 204
    assert client.get(f"{API}/eventos/{e2['id']}", headers=auth).status_code == 404
    assert client.delete(f"{API}/eventos/9999", headers=auth).status_code == 404


def test_eliminar_evento_con_dependencias_da_409(client, auth, crear_evento, monkeypatch):
    """Si la base rechaza el borrado por integridad referencial, el router responde 409 y no pierde el evento."""
    from sqlalchemy.exc import IntegrityError

    from app.application.evento_service import EventoService

    evento = crear_evento()

    def _rechazar(self, evento_id):
        raise IntegrityError("DELETE", {}, Exception("FK"))

    monkeypatch.setattr(EventoService, "eliminar", _rechazar)
    r = client.delete(f"{API}/eventos/{evento['id']}", headers=auth)
    assert r.status_code == 409
    assert "No se puede eliminar" in r.json()["detail"]
    assert client.get(f"{API}/eventos/{evento['id']}", headers=auth).status_code == 200


def test_entidades_de_dominio_validan_invariantes():
    with pytest.raises(ValueError):
        Evento(id=None, administrador_id=1, nombre="x", fecha=date.today(), aforo_maximo=0)
    with pytest.raises(ValueError):
        Comision(id=None, promotor_id=1, evento_id=1, porcentaje=Decimal("101"))
    with pytest.raises(ValueError):
        Comision(id=None, promotor_id=1, evento_id=1, porcentaje=Decimal("10"), monto=Decimal("-1"))


# ------------------------------------------------------------------ invitados y promotores
def test_invitados_permisos_y_aislamiento_entre_promotores(client, auth, crear_evento, crear_usuario, promotor, puerta):
    evento = crear_evento()
    otro = crear_usuario("otro@nightlife.io", "Promotor")
    propio = _invitado(client, promotor["headers"], evento["id"], promotor["id"], "Mio")
    # un promotor no puede registrar a nombre de otro: se fuerza su id
    forzado = _invitado(client, promotor["headers"], evento["id"], otro["id"], "Forzado")
    assert forzado["promotor_id"] == promotor["id"]
    ajeno = _invitado(client, otro["headers"], evento["id"], otro["id"], "Ajeno")

    lista = client.get(f"{API}/invitados?promotor_id={otro['id']}", headers=promotor["headers"]).json()
    assert lista["total"] == 2 and {i["nombre"] for i in lista["items"]} == {"Mio", "Forzado"}
    admin_lista = client.get(f"{API}/invitados?evento_id={evento['id']}&promotor_id={otro['id']}", headers=auth).json()
    assert admin_lista["total"] == 1 and admin_lista["items"][0]["nombre"] == "Ajeno"

    assert client.get(f"{API}/invitados/{propio['id']}", headers=promotor["headers"]).status_code == 200
    assert client.get(f"{API}/invitados/{ajeno['id']}", headers=promotor["headers"]).status_code == 404
    assert client.get(f"{API}/invitados/{ajeno['id']}", headers=auth).status_code == 200
    assert client.get(f"{API}/invitados/9999", headers=auth).status_code == 404

    assert client.get(f"{API}/invitados/resumen?evento_id={evento['id']}", headers=promotor["headers"]).json() == {"total": 2, "ingresaron": 0, "pendientes": 2}
    assert client.get(f"{API}/invitados/resumen?evento_id={evento['id']}", headers=auth).json()["total"] == 3
    assert client.get(f"{API}/invitados/resumen?evento_id={evento['id']}&promotor_id={otro['id']}", headers=auth).json()["total"] == 1

    assert client.post(f"{API}/invitados", json={"nombre": "x", "evento_id": evento["id"], "promotor_id": promotor["id"]}, headers=puerta["headers"]).status_code == 403
    assert client.delete(f"{API}/invitados/{ajeno['id']}", headers=promotor["headers"]).status_code == 404
    assert client.delete(f"{API}/invitados/{propio['id']}", headers=promotor["headers"]).status_code == 204
    assert client.delete(f"{API}/invitados/{propio['id']}", headers=auth).status_code == 404


def test_registrar_invitado_valida_evento_y_rol_del_promotor(client, auth, crear_evento, puerta, promotor):
    evento = crear_evento()
    body = {"nombre": "X", "evento_id": evento["id"], "promotor_id": promotor["id"]}
    assert client.post(f"{API}/invitados", json={**body, "evento_id": 9999}, headers=auth).status_code == 404
    assert client.post(f"{API}/invitados", json={**body, "promotor_id": 9999}, headers=auth).status_code == 404
    r = client.post(f"{API}/invitados", json={**body, "promotor_id": puerta["id"]}, headers=auth)
    assert r.status_code == 422 and "Promotor" in r.json()["detail"]


def test_meta_del_promotor(client, auth, crear_evento, promotor):
    evento = crear_evento()
    h = promotor["headers"]
    assert client.get(f"{API}/promotores/me/meta?evento_id={evento['id']}", headers=h).json() == {"evento_id": evento["id"], "objetivo": None}
    assert client.put(f"{API}/promotores/me/meta", json={"evento_id": evento["id"], "objetivo": 40}, headers=h).json()["objetivo"] == 40
    assert client.put(f"{API}/promotores/me/meta", json={"evento_id": evento["id"], "objetivo": 60}, headers=h).json()["objetivo"] == 60
    assert client.get(f"{API}/promotores/me/meta?evento_id={evento['id']}", headers=h).json()["objetivo"] == 60
    assert client.put(f"{API}/promotores/me/meta", json={"evento_id": 9999, "objetivo": 5}, headers=h).status_code == 404
    assert client.get(f"{API}/promotores/me/meta?evento_id={evento['id']}", headers=auth).status_code == 403


# ------------------------------------------------------------------ comisiones
def test_comisiones_ciclo_y_visibilidad(client, auth, crear_evento, crear_usuario, promotor, puerta):
    evento = crear_evento()
    otro = crear_usuario("otro@nightlife.io", "Promotor")
    c1 = client.post(f"{API}/comisiones", json={"promotor_id": promotor["id"], "evento_id": evento["id"], "porcentaje": 10}, headers=auth)
    assert c1.status_code == 201
    c2 = client.post(f"{API}/comisiones", json={"promotor_id": otro["id"], "evento_id": evento["id"], "porcentaje": 5}, headers=auth).json()
    base = {"promotor_id": promotor["id"], "evento_id": evento["id"], "porcentaje": 10}
    assert client.post(f"{API}/comisiones", json={**base, "promotor_id": 9999}, headers=auth).status_code == 404
    assert client.post(f"{API}/comisiones", json={**base, "promotor_id": puerta["id"]}, headers=auth).status_code == 422
    assert client.post(f"{API}/comisiones", json={**base, "evento_id": 9999}, headers=auth).status_code == 404
    assert client.post(f"{API}/comisiones", json=base, headers=promotor["headers"]).status_code == 403

    vistas = client.get(f"{API}/comisiones?promotor_id={otro['id']}", headers=promotor["headers"]).json()
    assert [c["promotor_id"] for c in vistas] == [promotor["id"]]
    assert len(client.get(f"{API}/comisiones", headers=auth).json()) == 2
    assert len(client.get(f"{API}/comisiones?evento_id={evento['id']}&estado=pendiente", headers=auth).json()) == 2
    assert client.get(f"{API}/comisiones?estado=liquidada", headers=auth).json() == []

    liq = client.put(f"{API}/comisiones/{c2['id']}", json={"estado": "liquidada"}, headers=auth).json()
    assert liq["estado"] == "liquidada" and liq["fecha_liquidacion"]
    again = client.put(f"{API}/comisiones/{c2['id']}", json={"monto": 1000}, headers=auth).json()
    assert again["fecha_liquidacion"] == liq["fecha_liquidacion"] and Decimal(str(again["monto"])) == 1000
    assert len(client.get(f"{API}/comisiones?estado=liquidada", headers=auth).json()) == 1
    assert client.put(f"{API}/comisiones/9999", json={"estado": "liquidada"}, headers=auth).status_code == 404


def test_comision_atipica_genera_alerta_y_alertas_crud(client, auth, crear_evento, promotor):
    evento = crear_evento()
    for monto in (100000, 110000, 90000, 105000):  # historial de comisiones liquidadas con algo de variación
        cid = client.post(f"{API}/comisiones", json={"promotor_id": promotor["id"], "evento_id": evento["id"], "porcentaje": 10}, headers=auth).json()["id"]
        client.put(f"{API}/comisiones/{cid}", json={"monto": monto, "estado": "liquidada"}, headers=auth)
    nueva = client.post(f"{API}/comisiones", json={"promotor_id": promotor["id"], "evento_id": evento["id"], "porcentaje": 10}, headers=auth).json()["id"]
    client.put(f"{API}/comisiones/{nueva}", json={"monto": 9_000_000}, headers=auth)

    alertas = client.get(f"{API}/alertas?evento_id={evento['id']}", headers=auth).json()
    assert alertas["total"] >= 1
    alerta = alertas["items"][0]
    assert alerta["tipo_alerta"] == "comision_atipica" and alerta["estado"] == "activa"
    assert client.get(f"{API}/alertas?nivel={alerta['nivel']}&estado=activa", headers=auth).json()["total"] >= 1
    otro_nivel = "bajo" if alerta["nivel"] != "bajo" else "alto"
    assert client.get(f"{API}/alertas?nivel={otro_nivel}", headers=auth).json()["total"] == 0
    assert client.get(f"{API}/alertas/{alerta['id']}", headers=auth).json()["id"] == alerta["id"]
    res = client.put(f"{API}/alertas/{alerta['id']}", json={"estado": "resuelta"}, headers=auth)
    assert res.status_code == 200 and res.json()["estado"] == "resuelta"
    assert client.get(f"{API}/alertas?estado=activa&evento_id={evento['id']}", headers=auth).json()["total"] == alertas["total"] - 1
    assert client.get(f"{API}/alertas/9999", headers=auth).status_code == 404
    assert client.put(f"{API}/alertas/9999", json={"estado": "resuelta"}, headers=auth).status_code == 404
    assert client.get(f"{API}/alertas", headers=promotor["headers"]).status_code == 403


# ------------------------------------------------------------------ accesos
def test_accesos_cortesia_listado_anulacion_y_eliminacion(client, auth, crear_evento, puerta, promotor):
    evento = crear_evento(aforo=2)
    h = puerta["headers"]
    cort = {"evento_id": evento["id"], "tipo": "cortesia_manual", "justificacion": "VIP del dueño", "nombre_cortesia": "Pepe"}
    r = client.post(f"{API}/accesos", json=cort, headers=h)
    assert r.status_code == 201 and r.json()["acceso"]["resultado"] == "valido" and r.json()["aforo_actual"] == 1
    assert client.post(f"{API}/accesos", json={"evento_id": evento["id"], "tipo": "cortesia_manual", "justificacion": "x"}, headers=h).status_code == 422
    assert client.post(f"{API}/accesos", json={"evento_id": evento["id"], "tipo": "cortesia_manual", "nombre_cortesia": "x"}, headers=h).status_code == 422
    assert client.post(f"{API}/accesos", json={"evento_id": evento["id"], "tipo": "qr"}, headers=h).status_code == 422
    assert client.post(f"{API}/accesos", json={**cort, "evento_id": 9999}, headers=h).status_code == 404
    assert client.post(f"{API}/accesos", json={"evento_id": 9999, "qr_code": "NLD-1-AAAAAAAAAAAAAAAA"}, headers=h).status_code == 404
    # justificación solo espacios: el esquema la acepta pero el servicio la rechaza
    assert client.post(f"{API}/accesos", json={**cort, "justificacion": "   "}, headers=h).status_code == 422

    client.post(f"{API}/accesos", json={**cort, "nombre_cortesia": "Ana"}, headers=h)
    lleno = client.post(f"{API}/accesos", json={**cort, "nombre_cortesia": "Luz"}, headers=h).json()
    assert lleno["acceso"]["resultado"] == "rechazado"

    # QR de otro evento -> rechazado
    otro_ev = crear_evento("Otro")
    inv = _invitado(client, auth, otro_ev["id"], promotor["id"])
    assert client.post(f"{API}/accesos", json={"evento_id": evento["id"], "qr_code": inv["qr_code"]}, headers=h).json()["acceso"]["resultado"] == "rechazado"
    # QR válido y luego duplicados con alerta ALTA (notificación deduplicada)
    ev3 = crear_evento("Tres", aforo=10)
    inv3 = _invitado(client, auth, ev3["id"], promotor["id"])
    assert client.post(f"{API}/accesos", json={"evento_id": ev3["id"], "qr_code": inv3["qr_code"]}, headers=h).json()["acceso"]["resultado"] == "valido"
    for _ in range(2):
        dup = client.post(f"{API}/accesos", json={"evento_id": ev3["id"], "qr_code": inv3["qr_code"]}, headers=h).json()
        assert dup["acceso"]["resultado"] == "duplicado"
        assert dup["alertas_generadas"] and dup["alertas_generadas"][0]["nivel"] == "alto"
    assert client.get(f"{API}/invitados/resumen?evento_id={ev3['id']}", headers=auth).json()["ingresaron"] == 1

    todos = client.get(f"{API}/accesos", headers=h).json()
    assert todos["total"] == len(todos["items"]) >= 7
    por_evento = client.get(f"{API}/accesos?evento_id={evento['id']}&limit=2&page=2", headers=h).json()
    assert por_evento["total"] == 4 and len(por_evento["items"]) == 2
    aid = todos["items"][0]["id"]
    assert client.get(f"{API}/accesos/{aid}", headers=h).json()["id"] == aid
    assert client.get(f"{API}/accesos/9999", headers=h).status_code == 404

    validos = [a for a in client.get(f"{API}/accesos?evento_id={evento['id']}&limit=100", headers=h).json()["items"] if a["resultado"] == "valido"]
    primero = validos[-1]
    assert client.put(f"{API}/accesos/{primero['id']}", headers=h).json()["resultado"] == "rechazado"
    assert client.put(f"{API}/accesos/9999", headers=h).status_code == 404
    assert client.delete(f"{API}/accesos/{primero['id']}", headers=h).status_code == 403
    assert client.delete(f"{API}/accesos/{primero['id']}", headers=auth).status_code == 204
    assert client.delete(f"{API}/accesos/{primero['id']}", headers=auth).status_code == 404
    tipos = {a["tipo_alerta"] for a in client.get(f"{API}/alertas", headers=auth).json()["items"]}
    assert "cortesia_duplicada" in tipos


def test_resumen_e_incidencias_de_puerta(client, auth, crear_evento, puerta, promotor):
    evento = crear_evento(aforo=4)
    h = puerta["headers"]
    inv = _invitado(client, auth, evento["id"], promotor["id"])
    for _ in range(2):
        client.post(f"{API}/accesos", json={"evento_id": evento["id"], "qr_code": inv["qr_code"]}, headers=h)
    client.post(f"{API}/accesos", json={"evento_id": evento["id"], "qr_code": "NLD-%d-BBBBBBBBBBBBBBBB" % evento["id"]}, headers=h)
    res = client.get(f"{API}/accesos/resumen?evento_id={evento['id']}", headers=h).json()
    assert (res["accesos_validos"], res["accesos_duplicados"], res["accesos_rechazados"], res["porcentaje_aforo"]) == (1, 1, 1, 0.25)
    assert res["evento_nombre"] == evento["nombre"]
    assert client.get(f"{API}/accesos/resumen?evento_id=9999", headers=h).status_code == 404

    cuerpo = {"evento_id": evento["id"], "tipo": "nombre_diferente", "persona": "  Carlos  ", "descripcion": "  El nombre no coincide  "}
    creada = client.post(f"{API}/accesos/incidencias", json=cuerpo, headers=h)
    assert creada.status_code == 201
    assert creada.json()["persona"] == "Carlos" and creada.json()["descripcion"] == "El nombre no coincide" and creada.json()["usuario_id"] == puerta["id"]
    sin_persona = client.post(f"{API}/accesos/incidencias", json={**cuerpo, "persona": "   "}, headers=h).json()
    assert sin_persona["persona"] is None
    assert client.post(f"{API}/accesos/incidencias", json={**cuerpo, "descripcion": "  a "}, headers=h).status_code == 422
    assert client.post(f"{API}/accesos/incidencias", json={**cuerpo, "evento_id": 9999}, headers=h).status_code == 404
    assert client.post(f"{API}/accesos/incidencias", json={**cuerpo, "tipo": "inventada"}, headers=h).status_code == 422
    assert len(client.get(f"{API}/accesos/incidencias?evento_id={evento['id']}&limit=1", headers=h).json()) == 1
    assert len(client.get(f"{API}/accesos/incidencias?evento_id={evento['id']}", headers=h).json()) == 2


# ------------------------------------------------------------------ dashboard
def test_dashboard_resumen_niveles_y_recomendaciones(client, auth, crear_evento, promotor, puerta, db_session):
    evento = crear_evento(aforo=10)
    h = puerta["headers"]
    url = f"{API}/dashboard/eventos/{evento['id']}/resumen"
    base = client.get(url, headers=auth).json()
    assert base["nivel_riesgo_general"] == "bajo" and "parámetros normales" in base["recomendacion"]
    assert client.get(f"{API}/dashboard/eventos/9999/resumen", headers=auth).status_code == 404
    assert client.get(url, headers=h).status_code == 403

    for i in range(7):
        inv = _invitado(client, auth, evento["id"], promotor["id"], f"I{i}")
        client.post(f"{API}/accesos", json={"evento_id": evento["id"], "qr_code": inv["qr_code"]}, headers=h)

    def _resolver_activas():
        for a in db_session.query(AlertaRiesgoModel).all():
            a.estado = EstadoAlerta.RESUELTA.value
        db_session.commit()

    _resolver_activas()
    r = client.get(url, headers=auth).json()
    assert r["accesos_validos"] == 7 and "límite" in r["recomendacion"]

    # un duplicado genera alerta alta; se resuelve y queda una media -> nivel medio con aviso de reingreso
    inv0 = client.get(f"{API}/invitados?evento_id={evento['id']}", headers=auth).json()["items"][0]
    client.post(f"{API}/accesos", json={"evento_id": evento["id"], "qr_code": inv0["qr_code"]}, headers=h)
    _resolver_activas()
    db_session.add(AlertaRiesgoModel(evento_id=evento["id"], tipo_alerta=TipoAlerta.SOBREAFORO.value, nivel=NivelAlerta.MEDIO.value, descripcion="m", estado="activa"))
    db_session.commit()
    r = client.get(url, headers=auth).json()
    assert r["nivel_riesgo_general"] == "medio" and r["accesos_duplicados"] == 1 and "reingreso" in r["recomendacion"]

    db_session.add(AlertaRiesgoModel(evento_id=evento["id"], tipo_alerta=TipoAlerta.SOBREAFORO.value, nivel=NivelAlerta.ALTO.value, descripcion="a", estado="activa"))
    db_session.commit()
    r = client.get(url, headers=auth).json()
    assert r["nivel_riesgo_general"] == "alto" and "Riesgo alto" in r["recomendacion"]

    cid = client.post(f"{API}/comisiones", json={"promotor_id": promotor["id"], "evento_id": evento["id"], "porcentaje": 10}, headers=auth).json()["id"]
    client.put(f"{API}/comisiones/{cid}", json={"monto": 500, "estado": "liquidada"}, headers=auth)
    cid2 = client.post(f"{API}/comisiones", json={"promotor_id": promotor["id"], "evento_id": evento["id"], "porcentaje": 10}, headers=auth).json()["id"]
    client.put(f"{API}/comisiones/{cid2}", json={"monto": 200}, headers=auth)
    r = client.get(url, headers=auth).json()
    assert r["comisiones_liquidadas"] == 500 and r["comisiones_pendientes"] == 200


def test_dashboard_informe_con_y_sin_ia(client, auth, crear_evento):
    evento = crear_evento()
    r = client.post(f"{API}/dashboard/eventos/{evento['id']}/informe", headers=auth)
    assert r.status_code == 200 and "narrativa" in r.json() and "recomendaciones_reglas" not in r.json()
    r2 = client.post(f"{API}/dashboard/eventos/{evento['id']}/informe", json={"usar_ia": False}, headers=auth)
    assert r2.status_code == 200


def test_raiz_y_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert "funcionando" in client.get("/").json()["message"]
