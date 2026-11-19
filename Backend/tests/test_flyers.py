"""Flyers de eventos guardados en la base de datos (subida por trozos y entrega con Range)."""
import os
from uuid import uuid4

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
MP4_CABECERA = b"\x00\x00\x00\x18ftypmp42"


def _video(n_bytes: int) -> bytes:
    return MP4_CABECERA + os.urandom(n_bytes - len(MP4_CABECERA))


def _subir_por_partes(client, auth, evento_id: int, contenido: bytes, tipo: str, trozo: int = 3_500_000):
    subida = uuid4().hex
    partes = [contenido[i:i + trozo] for i in range(0, len(contenido), trozo)]
    ultima = None
    for orden, parte in enumerate(partes):
        ultima = client.post(
            f"/api/v1/eventos/{evento_id}/flyer/partes",
            data={"subida": subida, "orden": orden, "total": len(partes), "tipo": tipo, "tamano_total": len(contenido)},
            files={"archivo": ("flyer", parte, tipo)},
            headers=auth,
        )
        assert ultima.status_code == 200, ultima.text
    return ultima.json()


def test_flyer_pequeno_se_guarda_en_bd_y_se_entrega_publico(client, auth, crear_evento):
    evento = crear_evento()
    r = client.post(f"/api/v1/eventos/{evento['id']}/flyer", files={"archivo": ("a.png", PNG, "image/png")}, headers=auth)
    assert r.status_code == 200, r.text
    url = r.json()["flyer_url"]
    assert url.startswith(f"/api/v1/eventos/{evento['id']}/flyer/") and url.endswith(".png")
    publico = client.get(url)  # sin token: lo ven los clientes
    assert publico.status_code == 200
    assert publico.content == PNG
    assert publico.headers["content-type"] == "image/png"
    assert "immutable" in publico.headers["cache-control"]


def test_video_grande_por_partes_y_entrega_por_rangos(client, auth, crear_evento):
    evento = crear_evento()
    contenido = _video(8_000_000)
    guardado = _subir_por_partes(client, auth, evento["id"], contenido, "video/mp4")
    url = guardado["flyer_url"]
    assert url.endswith(".mp4")

    primero = client.get(url, headers={"Range": "bytes=0-99"})
    assert primero.status_code == 206
    assert primero.content == contenido[:100]
    assert primero.headers["content-range"] == f"bytes 0-99/{len(contenido)}"

    cruce = client.get(url, headers={"Range": "bytes=3499990-3500010"})  # cruza el límite entre dos partes
    assert cruce.status_code == 206 and cruce.content == contenido[3499990:3500011]

    abierto = client.get(url, headers={"Range": "bytes=0-"})  # el navegador pide todo: se entrega un trozo
    assert abierto.status_code == 206
    assert len(abierto.content) <= 4 * 1024 * 1024
    assert abierto.content == contenido[: len(abierto.content)]

    ultimos = client.get(url, headers={"Range": "bytes=-50"})
    assert ultimos.status_code == 206 and ultimos.content == contenido[-50:]

    fuera = client.get(url, headers={"Range": f"bytes={len(contenido) + 10}-"})
    assert fuera.status_code == 416


def test_reemplazar_y_quitar_flyer(client, auth, crear_evento):
    evento = crear_evento()
    r1 = client.post(f"/api/v1/eventos/{evento['id']}/flyer", files={"archivo": ("a.png", PNG, "image/png")}, headers=auth)
    primero = r1.json()["flyer_url"]
    nuevo_png = PNG + b"\x01" * 50
    r2 = client.post(f"/api/v1/eventos/{evento['id']}/flyer", files={"archivo": ("b.png", nuevo_png, "image/png")}, headers=auth)
    segundo = r2.json()["flyer_url"]
    assert segundo != primero
    assert client.get(segundo).content == nuevo_png

    borrado = client.delete(f"/api/v1/eventos/{evento['id']}/flyer", headers=auth)
    assert borrado.status_code == 200 and borrado.json()["flyer_url"] is None
    assert client.get(segundo).status_code == 404


def test_validaciones_de_flyer(client, auth, crear_evento):
    evento = crear_evento()
    base = f"/api/v1/eventos/{evento['id']}/flyer"
    tipo_malo = client.post(base, files={"archivo": ("a.pdf", b"%PDF-1.4", "application/pdf")}, headers=auth)
    assert tipo_malo.status_code == 415
    falso = client.post(base, files={"archivo": ("a.png", b"esto no es una imagen", "image/png")}, headers=auth)
    assert falso.status_code == 415
    grande = client.post(
        f"{base}/partes",
        data={"subida": uuid4().hex, "orden": 0, "total": 2, "tipo": "image/png", "tamano_total": 6_000_000},
        files={"archivo": ("a.png", PNG, "image/png")},
        headers=auth,
    )
    assert grande.status_code == 413  # las imágenes de más de 4 MB deben comprimirse antes de subir
    sin_permiso = client.post(base, files={"archivo": ("a.png", PNG, "image/png")})
    assert sin_permiso.status_code in (401, 403)


def test_subida_incompleta_no_publica_el_flyer(client, auth, crear_evento):
    evento = crear_evento()
    contenido = _video(5_000_000)
    r = client.post(
        f"/api/v1/eventos/{evento['id']}/flyer/partes",
        data={"subida": uuid4().hex, "orden": 0, "total": 2, "tipo": "video/mp4", "tamano_total": len(contenido)},
        files={"archivo": ("v.mp4", contenido[:3_500_000], "video/mp4")},
        headers=auth,
    )
    assert r.status_code == 200 and r.json()["flyer_url"] is None


def test_eliminar_evento_borra_su_flyer(client, auth, crear_evento):
    evento = crear_evento()
    r = client.post(f"/api/v1/eventos/{evento['id']}/flyer", files={"archivo": ("a.png", PNG, "image/png")}, headers=auth)
    url = r.json()["flyer_url"]
    assert client.delete(f"/api/v1/eventos/{evento['id']}", headers=auth).status_code == 204
    assert client.get(url).status_code == 404
