import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models.notificacion_model import NotificacionModel


@pytest.fixture
def avisos_whatsapp(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    avisos: list[dict] = []
    monkeypatch.setattr("app.api.v1.inventario_router.notificar_stock_bajo", lambda d: avisos.append(d))
    return avisos


def _crear(client: TestClient, auth, **cambios) -> dict:
    cuerpo = {"nombre": "Aguardiente", "categoria": "Licores", "cantidad": 10, "unidad": "botellas", "stock_minimo": 4, "costo_unitario": 80000}
    cuerpo.update(cambios)
    respuesta = client.post("/api/v1/inventario", json=cuerpo, headers=auth)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _movimiento(client: TestClient, auth, item_id: int, tipo: str, cantidad: float, **extra):
    return client.post(f"/api/v1/inventario/{item_id}/movimientos", json={"tipo": tipo, "cantidad": cantidad, **extra}, headers=auth)


def _no_leidas(client: TestClient, auth) -> list[dict]:
    return client.get("/api/v1/notificaciones?solo_no_leidas=true", headers=auth).json()["items"]


def test_producto_nuevo_registra_existencias_iniciales(client: TestClient, auth, avisos_whatsapp) -> None:
    item = _crear(client, auth)
    assert item["estado_stock"] == "ok" and float(item["costo_unitario"]) == 80000
    historial = client.get(f"/api/v1/inventario/{item['id']}/movimientos", headers=auth).json()
    assert [(m["tipo"], float(m["cantidad_nueva"])) for m in historial] == [("entrada", 10.0)]
    assert avisos_whatsapp == [] and _no_leidas(client, auth) == []


def test_salidas_cruzan_minimo_y_agotan_con_notificaciones(client: TestClient, auth, avisos_whatsapp) -> None:
    item = _crear(client, auth)
    bajo = _movimiento(client, auth, item["id"], "salida", 7, motivo="Servicio de la noche")
    assert bajo.status_code == 201 and bajo.json()["item"]["estado_stock"] == "bajo"
    assert len(avisos_whatsapp) == 1
    avisos = _no_leidas(client, auth)
    assert [a["tipo"] for a in avisos] == ["inventario_bajo"] and avisos[0]["nivel"] == "alerta"

    # Seguir bajando sin cruzar un umbral nuevo no repite el aviso.
    _movimiento(client, auth, item["id"], "salida", 1)
    assert len(avisos_whatsapp) == 1 and len(_no_leidas(client, auth)) == 1

    agotado = _movimiento(client, auth, item["id"], "consumo", 2)
    assert agotado.json()["item"]["estado_stock"] == "agotado"
    assert len(avisos_whatsapp) == 2
    assert {a["tipo"] for a in _no_leidas(client, auth)} == {"inventario_bajo", "inventario_agotado"}

    # Reponer resuelve las alertas abiertas del producto.
    repuesto = _movimiento(client, auth, item["id"], "entrada", 12, motivo="Compra a proveedor")
    assert repuesto.json()["item"]["estado_stock"] == "ok"
    assert _no_leidas(client, auth) == []


def test_no_se_puede_sacar_mas_de_lo_que_hay(client: TestClient, auth) -> None:
    item = _crear(client, auth, cantidad=3)
    respuesta = _movimiento(client, auth, item["id"], "salida", 5)
    assert respuesta.status_code == 409 and "suficientes" in respuesta.json()["detail"]
    assert client.get("/api/v1/inventario", headers=auth).json()[0]["cantidad"] in ("3.00", 3, 3.0)


def test_ajuste_fija_el_conteo_fisico(client: TestClient, auth) -> None:
    item = _crear(client, auth)
    ajuste = _movimiento(client, auth, item["id"], "ajuste", 7, motivo="Conteo de cierre")
    mov = ajuste.json()["movimiento"]
    assert (float(mov["cantidad_anterior"]), float(mov["cantidad_nueva"]), float(mov["cantidad"])) == (10.0, 7.0, 3.0)


def test_validaciones_de_movimientos(client: TestClient, auth) -> None:
    item = _crear(client, auth)
    assert _movimiento(client, auth, item["id"], "entrada", 0).status_code == 422
    assert _movimiento(client, auth, item["id"], "regalo", 2).status_code == 422
    assert _movimiento(client, auth, 9999, "entrada", 2).status_code == 404
    assert _movimiento(client, auth, item["id"], "consumo", 1, evento_id=9999).status_code == 404


def test_consumo_por_evento_y_resumen(client: TestClient, auth, crear_evento) -> None:
    evento = crear_evento()
    ron = _crear(client, auth, nombre="Ron", cantidad=20, stock_minimo=5, costo_unitario=60000)
    hielo = _crear(client, auth, nombre="Hielo", categoria="Insumos", cantidad=50, unidad="bolsas", stock_minimo=10, costo_unitario=None)
    _movimiento(client, auth, ron["id"], "consumo", 6, evento_id=evento["id"])
    _movimiento(client, auth, ron["id"], "consumo", 2, evento_id=evento["id"])
    _movimiento(client, auth, hielo["id"], "salida", 8, evento_id=evento["id"])

    consumo = client.get(f"/api/v1/inventario/eventos/{evento['id']}/consumo", headers=auth).json()
    assert {c["nombre"]: float(c["cantidad"]) for c in consumo} == {"Ron": 8.0, "Hielo": 8.0}
    assert client.get("/api/v1/inventario/eventos/9999/consumo", headers=auth).status_code == 404

    resumen = client.get("/api/v1/inventario/resumen", headers=auth).json()
    assert resumen["productos"] == 2 and resumen["agotados"] == 0
    assert float(resumen["valor_total"]) == 12 * 60000  # solo valora lo que tiene costo
    assert resumen["movimientos_hoy"] >= 5
    assert resumen["mayor_consumo_7d"][0]["cantidad"] in ("8.00", 8, 8.0)
    assert {c["categoria"] for c in resumen["categorias"]} == {"Licores", "Insumos"}


def test_filtros_exportacion_y_borrado(client: TestClient, auth) -> None:
    a = _crear(client, auth, nombre="Cerveza", cantidad=2, stock_minimo=5)
    _crear(client, auth, nombre="Tónica", categoria="Mezcladores", cantidad=30, stock_minimo=5)
    assert [i["nombre"] for i in client.get("/api/v1/inventario?estado=bajo", headers=auth).json()] == ["Cerveza"]
    assert [i["nombre"] for i in client.get("/api/v1/inventario?categoria=Mezcladores", headers=auth).json()] == ["Tónica"]
    assert float(client.get("/api/v1/inventario?estado=bajo", headers=auth).json()[0]["reposicion_sugerida"]) == 8.0

    csv = client.get("/api/v1/inventario/exportar.csv", headers=auth)
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    assert "Cerveza" in csv.text and "Reposición sugerida" in csv.text

    assert client.delete(f"/api/v1/inventario/{a['id']}", headers=auth).status_code == 204
    assert client.delete(f"/api/v1/inventario/{a['id']}", headers=auth).status_code == 404


def test_precio_de_venta_se_guarda_edita_y_se_exporta(client: TestClient, auth) -> None:
    item = _crear(client, auth, nombre="Tequila", costo_unitario=93000, precio_venta=250000)
    assert float(item["costo_unitario"]) == 93000 and float(item["precio_venta"]) == 250000

    cuerpo = {"nombre": "Tequila", "categoria": "Licores", "cantidad": 10, "unidad": "botellas", "stock_minimo": 4,
              "costo_unitario": 93000, "precio_venta": 280000}
    editado = client.put(f"/api/v1/inventario/{item['id']}", json=cuerpo, headers=auth)
    assert editado.status_code == 200 and float(editado.json()["precio_venta"]) == 280000

    sin_precio = client.put(f"/api/v1/inventario/{item['id']}", json={**cuerpo, "precio_venta": None}, headers=auth)
    assert sin_precio.json()["precio_venta"] is None
    negativo = client.put(f"/api/v1/inventario/{item['id']}", json={**cuerpo, "precio_venta": -1}, headers=auth)
    assert negativo.status_code == 422

    assert "Precio de venta" in client.get("/api/v1/inventario/exportar.csv", headers=auth).text


def test_solo_el_administrador_gestiona_el_inventario(client: TestClient, crear_usuario) -> None:
    puerta = crear_usuario("p@nightlife.io", "Puerta")
    assert client.get("/api/v1/inventario", headers=puerta["headers"]).status_code == 403
    assert client.get("/api/v1/inventario").status_code == 401


def test_notificaciones_marcar_leidas(client: TestClient, auth, db_session: Session, crear_usuario) -> None:
    item = _crear(client, auth, cantidad=2, stock_minimo=5)  # nace en mínimo -> aviso
    lista = client.get("/api/v1/notificaciones", headers=auth).json()
    assert lista["no_leidas"] == 1
    notificacion_id = lista["items"][0]["id"]

    otro = crear_usuario("otro@nightlife.io", "Puerta")
    assert client.post(f"/api/v1/notificaciones/{notificacion_id}/leer", headers=otro["headers"]).status_code == 404

    assert client.post(f"/api/v1/notificaciones/{notificacion_id}/leer", headers=auth).status_code == 200
    assert client.get("/api/v1/notificaciones", headers=auth).json()["no_leidas"] == 0

    _movimiento(client, auth, item["id"], "salida", 1)  # sigue bajo: no crea otra
    _crear(client, auth, nombre="Vodka", cantidad=1, stock_minimo=3)
    assert client.post("/api/v1/notificaciones/leer-todas", headers=auth).json()["marcadas"] == 1
    assert len(db_session.execute(select(NotificacionModel)).scalars().all()) == 2
