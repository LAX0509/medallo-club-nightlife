from fastapi.testclient import TestClient


def test_informe_de_jornada_con_cifras_reales_y_plan_b_local(client: TestClient, auth, crear_evento, crear_usuario) -> None:
    evento = crear_evento(aforo=4)
    puerta = crear_usuario("puerta@nightlife.io", "Puerta")
    promotor = crear_usuario("promo@nightlife.io", "Promotor")
    codigos = []
    for nombre in ("A", "B", "C"):
        codigos.append(client.post("/api/v1/invitados", json={"nombre": nombre, "evento_id": evento["id"], "promotor_id": promotor["id"]}, headers=auth).json()["qr_code"])
    for codigo in codigos:
        client.post("/api/v1/accesos", json={"evento_id": evento["id"], "qr_code": codigo}, headers=puerta["headers"])
    client.post("/api/v1/accesos", json={"evento_id": evento["id"], "qr_code": codigos[0]}, headers=puerta["headers"])  # duplicado
    client.post("/api/v1/inventario", json={"nombre": "Hielo", "cantidad": 0, "unidad": "bolsas", "stock_minimo": 5}, headers=auth)

    informe = client.post(f"/api/v1/dashboard/eventos/{evento['id']}/informe", json={"usar_ia": True}, headers=auth)
    assert informe.status_code == 200, informe.text
    datos = informe.json()
    assert datos["puerta"]["validos"] == 3 and datos["puerta"]["duplicados"] == 1
    assert datos["puerta"]["porcentaje_aforo"] == 0.75
    assert datos["alertas_activas"]["alto"] >= 1
    assert datos["inventario"]["agotados"] == ["Hielo"]
    narrativa = datos["narrativa"]
    assert narrativa["generado_con"] == "reglas"  # sin IA configurada se usa el plan B
    assert "3 personas" in narrativa["resumen"]
    assert any("Hielo" in r for r in narrativa["recomendaciones"])
    assert "recomendaciones_reglas" not in datos

    assert client.post("/api/v1/dashboard/eventos/9999/informe", headers=auth).status_code == 404
    assert client.post(f"/api/v1/dashboard/eventos/{evento['id']}/informe", headers=puerta["headers"]).status_code == 403
    # Una alerta de riesgo alto llegó a la campana del equipo.
    tipos = {n["tipo"] for n in client.get("/api/v1/notificaciones", headers=auth).json()["items"]}
    assert "alerta_riesgo" in tipos and "inventario_agotado" in tipos


def test_los_intentos_duplicados_repetidos_no_inundan_la_campana(client: TestClient, auth, crear_evento, crear_usuario) -> None:
    evento = crear_evento(aforo=50)
    puerta = crear_usuario("puerta@nightlife.io", "Puerta")
    promotor = crear_usuario("promo@nightlife.io", "Promotor")
    codigo = client.post("/api/v1/invitados", json={"nombre": "A", "evento_id": evento["id"], "promotor_id": promotor["id"]}, headers=auth).json()["qr_code"]
    for _ in range(6):
        client.post("/api/v1/accesos", json={"evento_id": evento["id"], "qr_code": codigo}, headers=puerta["headers"])
    avisos = [n for n in client.get("/api/v1/notificaciones", headers=auth).json()["items"] if n["tipo"] == "alerta_riesgo"]
    assert len(avisos) == 1  # 5 duplicados, una sola notificación abierta
