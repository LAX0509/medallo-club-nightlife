"""Flyers: validaciones de la subida por trozos, limpieza de archivos antiguos y entrega por rangos; más el motor de riesgo."""
from uuid import uuid4

import pytest

from app.application import flyer_service
from app.application.risk_engine import RiskEngine
from app.core.config import get_settings
from app.domain.enums import TipoAlerta
from app.infrastructure.models.evento_model import EventoModel

API = "/api/v1"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x01" * 300


def _evento(db_session, admin_id=1):
    from datetime import date

    ev = EventoModel(administrador_id=admin_id, nombre="E", fecha=date(2031, 1, 1), aforo_maximo=10, estado="planeado")
    db_session.add(ev)
    db_session.commit()
    return ev


def _parte(client, auth, evento_id, *, subida=None, orden=0, total=1, tipo="image/png", tamano=None, datos=PNG):
    return client.post(
        f"{API}/eventos/{evento_id}/flyer/partes",
        data={"subida": subida or uuid4().hex, "orden": orden, "total": total, "tipo": tipo, "tamano_total": len(datos) if tamano is None else tamano},
        files={"archivo": ("f", datos, tipo)},
        headers=auth,
    )


def test_validaciones_de_la_subida_por_partes(client, auth, crear_evento):
    ev = crear_evento()["id"]
    assert _parte(client, auth, ev, tipo="application/pdf").status_code == 415
    assert _parte(client, auth, ev, subida="../mala").status_code == 400
    assert _parte(client, auth, ev, total=0).status_code == 400
    assert _parte(client, auth, ev, orden=2, total=2).status_code == 400
    assert _parte(client, auth, ev, total=flyer_service.MAX_PARTES + 1).status_code == 400
    assert _parte(client, auth, ev, tamano=0).status_code == 413
    assert _parte(client, auth, ev, tamano=flyer_service.MAX_IMAGEN_BYTES + 1).status_code == 413
    assert _parte(client, auth, ev, tipo="video/mp4", datos=MP4, tamano=flyer_service.MAX_VIDEO_BYTES + 1).status_code == 413
    assert _parte(client, auth, ev, datos=b"", tamano=10).status_code == 413  # trozo vacío
    sin_cabecera = _parte(client, auth, ev, datos=b"esto no es una imagen")
    assert sin_cabecera.status_code == 415 and "no parece ser" in sin_cabecera.json()["detail"]
    # JPEG, WEBP, GIF y WEBM con su cabecera correcta
    for tipo, datos in (
        ("image/jpeg", b"\xff\xd8\xff\xe0" + b"0" * 50),
        ("image/webp", b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 50),
        ("image/gif", b"GIF89a" + b"0" * 50),
        ("video/webm", b"\x1a\x45\xdf\xa3" + b"0" * 50),
    ):
        assert _parte(client, auth, ev, tipo=tipo, datos=datos).status_code == 200, tipo
    # el administrador es el único que puede subir
    assert client.post(f"{API}/eventos/{ev}/flyer/partes", data={"subida": "a" * 8, "orden": 0, "total": 1, "tipo": "image/png", "tamano_total": 1}, files={"archivo": ("f", PNG, "image/png")}).status_code == 401


def test_flyer_de_evento_inexistente_y_tipo_no_permitido(client, auth, crear_evento):
    assert client.post(f"{API}/eventos/9999/flyer", files={"archivo": ("a.png", PNG, "image/png")}, headers=auth).status_code == 404
    assert _parte(client, auth, 9999).status_code == 404
    assert client.delete(f"{API}/eventos/9999/flyer", headers=auth).status_code == 404
    ev = crear_evento()["id"]
    assert client.post(f"{API}/eventos/{ev}/flyer", files={"archivo": ("a.pdf", b"%PDF", "application/pdf")}, headers=auth).status_code == 415
    # la imagen pequeña con cabecera falsa se rechaza dentro del servicio
    assert client.post(f"{API}/eventos/{ev}/flyer", files={"archivo": ("a.png", b"no-png", "image/png")}, headers=auth).status_code == 415


def test_archivo_incompleto_se_descarta(client, auth, crear_evento):
    ev = crear_evento()["id"]
    subida = uuid4().hex
    assert _parte(client, auth, ev, subida=subida, orden=0, total=2, tamano=len(PNG) + 100, datos=PNG).status_code == 200
    r = _parte(client, auth, ev, subida=subida, orden=1, total=2, tamano=len(PNG) + 100, datos=b"x" * 50)  # faltan 50 bytes
    assert r.status_code == 400 and "incompleto" in r.json()["detail"]
    assert client.get(f"{API}/eventos/{ev}/flyer/x.png").status_code == 404  # nada quedó publicado
    # un trozo reenviado (misma subida y orden) reemplaza al anterior en lugar de duplicarlo
    subida2 = uuid4().hex
    assert _parte(client, auth, ev, subida=subida2, orden=0, total=2, tamano=len(PNG) + 5, datos=PNG).status_code == 200
    assert _parte(client, auth, ev, subida=subida2, orden=0, total=2, tamano=len(PNG) + 5, datos=PNG).status_code == 200
    assert _parte(client, auth, ev, subida=subida2, orden=1, total=2, tamano=len(PNG) + 5, datos=b"12345").status_code == 200


def test_entrega_por_rangos_casos_limite(client, auth, crear_evento):
    ev = crear_evento()
    assert client.get(f"{API}/eventos/{ev['id']}/flyer/x.png").status_code == 404  # sin flyer
    subido = client.post(f"{API}/eventos/{ev['id']}/flyer", files={"archivo": ("v.mp4", MP4, "video/mp4")}, headers=auth).json()
    url = subido["flyer_url"]
    total = len(MP4)
    completo = client.get(url)
    assert completo.status_code == 200 and completo.content == MP4 and "content-range" not in completo.headers

    ultimos = client.get(url, headers={"Range": "bytes=-50"})
    assert ultimos.status_code == 206 and ultimos.content == MP4[-50:] and ultimos.headers["content-range"] == f"bytes {total - 50}-{total - 1}/{total}"
    mas_que_el_total = client.get(url, headers={"Range": f"bytes=-{total * 10}"})
    assert mas_que_el_total.status_code == 206 and mas_que_el_total.content == MP4
    fuera = client.get(url, headers={"Range": f"bytes={total + 10}-"})
    assert fuera.status_code == 416 and fuera.headers["content-range"] == f"bytes */{total}"
    cerrado = client.get(url, headers={"Range": "bytes=10-19"})
    assert cerrado.content == MP4[10:20]
    # rangos mal formados se ignoran y se entrega el archivo completo
    for raro in ("bytes=-", "items=0-5", "bytes=a-b"):
        assert client.get(url, headers={"Range": raro}).content == MP4

    # quitar el flyer limpia todo
    quitado = client.delete(f"{API}/eventos/{ev['id']}/flyer", headers=auth)
    assert quitado.status_code == 200 and quitado.json()["flyer_url"] is None
    assert client.get(url).status_code == 404


def test_servicio_borra_flyers_antiguos_de_disco_solo_dentro_de_la_carpeta(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(flyer_service, "_UPLOADS_DIR", tmp_path)
    viejo = tmp_path / "viejo.png"
    viejo.write_bytes(PNG)
    flyer_service._borrar_archivo_en_disco("/uploads/flyers/viejo.png")
    assert not viejo.exists()
    flyer_service._borrar_archivo_en_disco(None)
    flyer_service._borrar_archivo_en_disco("/api/v1/eventos/1/flyer/abc.png")  # flyer en BD: no toca el disco
    flyer_service._borrar_archivo_en_disco("/uploads/flyers/no-existe.png")
    afuera = tmp_path.parent / "afuera.txt"
    afuera.write_text("no borrar")
    flyer_service._borrar_archivo_en_disco("/uploads/flyers/../afuera.txt")  # Path(...).name evita salir de la carpeta
    assert afuera.exists()

    # al reemplazar un flyer antiguo en disco, se borra
    ev = _evento(db_session)
    ev.flyer_url = "/uploads/flyers/anterior.png"
    (tmp_path / "anterior.png").write_bytes(PNG)
    db_session.commit()
    flyer_service.guardar_completo(db_session, ev, "image/png", PNG)
    assert not (tmp_path / "anterior.png").exists() and ev.flyer_url.endswith(".png")

    def _sin_permiso(self):
        raise OSError("permiso denegado")

    (tmp_path / "bloqueado.png").write_bytes(PNG)
    monkeypatch.setattr(type(tmp_path), "unlink", _sin_permiso)
    flyer_service._borrar_archivo_en_disco("/uploads/flyers/bloqueado.png")  # un fallo del disco no rompe la subida


def test_leer_rango_y_limites_por_tipo(db_session):
    ev = _evento(db_session)
    assert flyer_service.leer_rango(db_session, ev.id, None, None) is None
    assert flyer_service.limite_para("video/mp4") == flyer_service.MAX_VIDEO_BYTES
    assert flyer_service.limite_para("image/png") == flyer_service.MAX_IMAGEN_BYTES
    assert flyer_service.cabecera_valida("video/mp4", b"\x00\x00\x00\x18ftyp") is False  # cabecera demasiado corta
    from app.infrastructure.models.evento_flyer_model import EventoFlyerModel

    db_session.add(EventoFlyerModel(evento_id=ev.id, subida="s" * 8, tipo="image/png", tamano=5))
    db_session.commit()
    assert flyer_service.leer_rango(db_session, ev.id, None, None) is None  # registro sin trozos: no hay nada que entregar
    flyer_service.guardar_completo(db_session, ev, "image/png", PNG)
    contenido, ini, fin, total, tipo = flyer_service.leer_rango(db_session, ev.id, 5, 9)
    assert (contenido, ini, fin, total, tipo) == (PNG[5:10], 5, 9, len(PNG), "image/png")


# ------------------------------------------------------------------ motor de riesgos
def test_motor_de_riesgo_comision_sin_variacion_y_tipo_de_alerta():
    motor = RiskEngine(get_settings())
    sin_historial = motor.evaluar_comision_atipica(monto_nuevo=1000, historico=[1, 2])
    assert sin_historial.es_atipica is False and sin_historial.z_score is None
    plano = motor.evaluar_comision_atipica(monto_nuevo=999999, historico=[100, 100, 100])
    assert plano.es_atipica is False and plano.z_score is None  # desviación 0: no se puede estandarizar
    normal = motor.evaluar_comision_atipica(monto_nuevo=101, historico=[100, 110, 90])
    assert normal.es_atipica is False and normal.z_score is not None
    desviacion = (200 / 3) ** 0.5  # desviación poblacional de [100, 110, 90]
    medio = motor.evaluar_comision_atipica(monto_nuevo=100 + 2.2 * desviacion, historico=[100, 110, 90])
    assert medio.es_atipica and medio.nivel.value == "medio"  # entre 2.0 y 3.0 desviaciones
    assert motor.evaluar_comision_atipica(monto_nuevo=100 - 3.5 * desviacion, historico=[100, 110, 90]).nivel.value == "alto"
    assert motor.evaluar_comision_atipica(monto_nuevo=10_000, historico=[100, 110, 90]).nivel.value == "alto"
    assert RiskEngine.tipo_alerta_para("sobreaforo") is TipoAlerta.SOBREAFORO
    with pytest.raises(ValueError):
        RiskEngine.tipo_alerta_para("inventada")
