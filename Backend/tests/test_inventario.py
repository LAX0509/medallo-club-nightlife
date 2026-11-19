from fastapi.testclient import TestClient


def test_inventory_alerts_only_when_crossing_minimum(
    client: TestClient,
    admin_token: str,
    monkeypatch,
) -> None:
    avisos = []
    monkeypatch.setattr(
        "app.api.v1.inventario_router.notificar_stock_bajo",
        lambda datos: avisos.append(datos),
    )
    headers = {"Authorization": f"Bearer {admin_token}"}
    producto = {
        "nombre": "Agua",
        "categoria": "Bebidas",
        "cantidad": 10,
        "unidad": "botellas",
        "stock_minimo": 5,
    }
    creado = client.post("/api/v1/inventario", json=producto, headers=headers)
    assert creado.status_code == 201
    assert avisos == []

    item_id = creado.json()["id"]
    producto["cantidad"] = 4
    bajo = client.put(f"/api/v1/inventario/{item_id}", json=producto, headers=headers)
    assert bajo.status_code == 200
    assert len(avisos) == 1
    assert avisos[0]["nombre"] == "Agua"
    assert avisos[0]["cantidad"] == 4.0

    producto["cantidad"] = 3
    sigue_bajo = client.put(f"/api/v1/inventario/{item_id}", json=producto, headers=headers)
    assert sigue_bajo.status_code == 200
    assert len(avisos) == 1

    producto["cantidad"] = 8
    repuesto = client.put(f"/api/v1/inventario/{item_id}", json=producto, headers=headers)
    assert repuesto.status_code == 200
    producto["cantidad"] = 2
    vuelve_a_bajar = client.put(f"/api/v1/inventario/{item_id}", json=producto, headers=headers)
    assert vuelve_a_bajar.status_code == 200
    assert len(avisos) == 2
