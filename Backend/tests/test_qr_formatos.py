import base64
import json

import pytest
from fastapi.testclient import TestClient

from app.application.qr_format import (
    FORMATOS_ESCRITURA,
    construir_payload_qr,
    leer_qr,
    normalizar_codigo_qr,
)

CODIGO = "NLD-17-AbcdefGhijkLmnoPqrs12345"


@pytest.mark.parametrize(
    "contenido, formato",
    [
        (CODIGO, "codigo"),
        (f"  {CODIGO}\n", "codigo"),
        (f"​{CODIGO}​", "codigo"),
        (CODIGO.replace("NLD-", "nld-"), "codigo"),
        (f"https://club.example/pase/{CODIGO}", "url"),
        (f"https://club.example/scan?code={CODIGO}&x=1", "url"),
        (f"medallo://pase/{CODIGO}", "esquema"),
        (f'{{"app":"medallo-club","v":1,"qr":"{CODIGO}"}}', "json"),
        (f'{{"data":{{"codigo":"{CODIGO}"}}}}', "json"),
        (base64.urlsafe_b64encode(json.dumps({"qr": CODIGO}).encode()).decode().rstrip("="), "base64"),
        (base64.b64encode(f"https://club.example/pase/{CODIGO}".encode()).decode(), "base64"),
        (f"Pase de Medallo Club\nCódigo: {CODIGO}\nGracias", "texto"),
        (f"https://club.example/pase/{CODIGO.replace('-', '%2D')}", "url"),
    ],
)
def test_detecta_formato_y_codigo(contenido: str, formato: str) -> None:
    lectura = leer_qr(contenido)
    assert (lectura.codigo, lectura.formato) == (CODIGO, formato)
    assert normalizar_codigo_qr(contenido) == CODIGO


@pytest.mark.parametrize("formato", FORMATOS_ESCRITURA)
def test_lo_que_se_escribe_se_puede_leer(formato: str) -> None:
    payload = construir_payload_qr(CODIGO, formato, base_url="https://club.example/", evento_id=17)
    assert leer_qr(payload).codigo == CODIGO


def test_rechaza_contenido_invalido() -> None:
    for malo in ["", "hola", "https://example.com/otra-cosa", "NLD-abc-corto", '{"qr":"no-es-un-codigo"}', "x" * 3000]:
        with pytest.raises(ValueError):
            leer_qr(malo)
    with pytest.raises(ValueError):
        construir_payload_qr("no-es-un-codigo", "codigo")
    with pytest.raises(ValueError):
        construir_payload_qr(CODIGO, "morse")


def _pase(client: TestClient, auth, crear_evento, crear_usuario) -> tuple[dict, dict]:
    evento = crear_evento()
    promotor = crear_usuario("promo@nightlife.io", "Promotor")
    invitado = client.post(
        "/api/v1/invitados", json={"nombre": "Luis Gómez", "evento_id": evento["id"], "promotor_id": promotor["id"]}, headers=auth
    ).json()
    return evento, invitado


def test_imagenes_qr_en_svg_y_png_y_todos_los_formatos(client: TestClient, auth, crear_evento, crear_usuario) -> None:
    _, invitado = _pase(client, auth, crear_evento, crear_usuario)
    codigo = invitado["qr_code"]
    svg = client.get(f"/api/v1/pases/{codigo}/qr.svg")
    assert svg.status_code == 200 and svg.headers["content-type"] == "image/svg+xml" and b"<svg" in svg.content
    png = client.get(f"/api/v1/pases/{codigo}/qr.png?formato=json&escala=6&descargar=true")
    assert png.status_code == 200 and png.content.startswith(b"\x89PNG")
    assert "attachment" in png.headers["content-disposition"]
    for formato in FORMATOS_ESCRITURA:
        assert client.get(f"/api/v1/pases/{codigo}/qr.svg?formato={formato}").status_code == 200
    assert client.get(f"/api/v1/pases/{codigo}/qr.svg?formato=morse").status_code == 422
    assert client.get(f"/api/v1/pases/{codigo}/qr.gif").status_code == 422
    assert client.get("/api/v1/pases/NLD-1-noexistenoexistenoexiste/qr.svg").status_code == 404


def test_pagina_publica_del_pase_y_calendario(client: TestClient, auth, crear_evento, crear_usuario) -> None:
    evento, invitado = _pase(client, auth, crear_evento, crear_usuario)
    pase = client.get(f"/api/v1/pases/{invitado['qr_code']}")
    assert pase.status_code == 200
    datos = pase.json()
    assert (datos["nombre"], datos["valido"], datos["reserva"]) == ("Luis Gómez", True, None)
    assert datos["evento_nombre"] == evento["nombre"]

    ics = client.get(f"/api/v1/pases/{invitado['qr_code']}/calendario.ics")
    assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VEVENT" in ics.text and f"SUMMARY:{evento['nombre']}" in ics.text
    assert client.get("/api/v1/pases/NLD-1-noexistenoexistenoexiste").status_code == 404
    assert client.get("/api/v1/pases/basura").status_code == 404


def test_formatos_publicos_y_lector_de_diagnostico(client: TestClient, auth, crear_usuario) -> None:
    formatos = client.get("/api/v1/qr/formatos").json()
    assert {f["formato"] for f in formatos} == set(FORMATOS_ESCRITURA)

    puerta = crear_usuario("puerta@nightlife.io", "Puerta")
    ok = client.post("/api/v1/qr/leer", json={"contenido": f"medallo://pase/{CODIGO}"}, headers=puerta["headers"])
    assert ok.status_code == 200 and ok.json() == {"codigo": CODIGO, "formato": "esquema"}
    assert client.post("/api/v1/qr/leer", json={"contenido": "nada"}, headers=puerta["headers"]).status_code == 422
    promotor = crear_usuario("promo@nightlife.io", "Promotor")
    assert client.post("/api/v1/qr/leer", json={"contenido": CODIGO}, headers=promotor["headers"]).status_code == 403


@pytest.mark.parametrize("formato", FORMATOS_ESCRITURA)
def test_puerta_acepta_el_pase_en_cualquier_formato(client: TestClient, auth, crear_evento, crear_usuario, formato: str) -> None:
    evento, invitado = _pase(client, auth, crear_evento, crear_usuario)
    puerta = crear_usuario("puerta@nightlife.io", "Puerta")
    contenido = construir_payload_qr(invitado["qr_code"], formato, base_url="https://club.example", evento_id=evento["id"])
    ingreso = client.post("/api/v1/accesos", json={"evento_id": evento["id"], "qr_code": contenido}, headers=puerta["headers"])
    assert ingreso.status_code == 201, ingreso.text
    assert ingreso.json()["acceso"]["resultado"] == "valido"
    repetido = client.post("/api/v1/accesos", json={"evento_id": evento["id"], "qr_code": contenido}, headers=puerta["headers"])
    assert repetido.json()["acceso"]["resultado"] == "duplicado"
