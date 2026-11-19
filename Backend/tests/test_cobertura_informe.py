"""Informe de cierre de jornada: cifras agregadas, recomendaciones por reglas y narrativa (con IA simulada validada)."""
import copy

import pytest

from app.application import informe_service as inf
from app.application.ia_client import IANoDisponible

API = "/api/v1"


def _base():
    return {
        "evento": {"id": 1, "nombre": "Retro", "fecha": "2030-01-01", "aforo_maximo": 100, "estado": "planeado"},
        "puerta": {"validos": 60, "duplicados": 0, "rechazados": 0, "cortesias_manuales": 0, "porcentaje_aforo": 0.6},
        "comisiones": {"pendiente": 0.0, "liquidada": 0.0},
        "alertas_activas": {"alto": 0, "medio": 0, "bajo": 0},
        "reservas": {"solicitudes": 0, "pendientes": 0, "garantizadas": 0, "canceladas": 0, "pases_emitidos": 0, "pases_usados": 0, "garantizadas_sin_llegada": 0},
        "inventario": {"agotados": [], "en_minimo": [], "mayor_consumo_evento": []},
        "sentimiento": {"conversaciones_7d": 0, "escaladas_abiertas": 0},
    }


def _con(**cambios):
    d = copy.deepcopy(_base())
    for ruta, valor in cambios.items():
        seccion, _, campo = ruta.partition("__")
        d[seccion][campo] = valor
    return d


@pytest.mark.parametrize(
    "cambios, fragmento",
    [
        ({"alertas_activas__alto": 2}, "2 alerta(s) de riesgo alto"),
        ({"puerta__porcentaje_aforo": 0.95}, "superó el 90 %"),
        ({"puerta__porcentaje_aforo": 0.2}, "asistencia fue baja"),
        ({"puerta__duplicados": 3}, "3 intentos con QR repetido"),
        ({"puerta__cortesias_manuales": 5}, "muchas cortesías manuales"),
        ({"reservas__garantizadas_sin_llegada": 2}, "2 reserva(s) garantizada(s) no llegaron"),
        ({"reservas__pendientes": 4}, "4 solicitud(es) de reserva pendientes"),
        ({"inventario__agotados": ["Hielo", "Ron"]}, "Repón antes del próximo evento: Hielo, Ron."),
        ({"inventario__en_minimo": ["Agua"]}, "nivel mínimo: Agua."),
        ({"comisiones__pendiente": 1500.0}, "comisiones de promotores pendientes"),
        ({"sentimiento__escaladas_abiertas": 3}, "3 conversación(es) escalada(s)"),
    ],
)
def test_cada_regla_de_recomendacion(cambios, fragmento):
    assert any(fragmento in r for r in inf.recomendaciones_locales(_con(**cambios)))


def test_recomendaciones_sin_hallazgos_y_prioridad_de_agotados_sobre_minimos():
    assert inf.recomendaciones_locales(_base()) == ["Operación dentro de parámetros normales: baja exposición a pérdidas y buen rendimiento operativo."]
    recs = inf.recomendaciones_locales(_con(inventario__agotados=["A"], inventario__en_minimo=["B"]))
    assert len(recs) == 1 and "A" in recs[0] and "B" not in recs[0]
    # aforo en 0 no se considera «asistencia baja» (la jornada aún no empieza)
    assert "asistencia fue baja" not in " ".join(inf.recomendaciones_locales(_con(puerta__porcentaje_aforo=0.0)))


def test_narrativa_local_incluye_solo_lo_que_ocurrio():
    base = inf.narrativa_local(_base())
    assert "ingresaron 60 personas (60% del aforo de 100)" in base and "No hay alertas de riesgo alto abiertas." in base
    assert "reserva" not in base and "QR repetido" not in base
    rica = inf.narrativa_local(_con(puerta__duplicados=2, puerta__rechazados=1, reservas__solicitudes=5, reservas__garantizadas=3, reservas__pendientes=1, reservas__canceladas=1, alertas_activas__alto=2))
    assert "2 intento(s) con QR repetido y 1 rechazo(s)" in rica and "3 garantizada(s), 1 pendiente(s) y 1 cancelada(s)" in rica and "2 alerta(s) de riesgo alto abierta(s)" in rica


class _IA:
    def __init__(self, respuesta=None, falla=None, disponible=True):
        self.respuesta, self.falla, self.disponible = respuesta, falla, disponible
        self.modelo = "modelo-falso"
        self.recibido = None

    def json(self, **kw):
        self.recibido = kw
        if self.falla:
            raise self.falla
        return self.respuesta


def _informe():
    d = _base()
    d["recomendaciones_reglas"] = inf.recomendaciones_locales(d)
    return d


def test_generar_narrativa_plan_b_cuando_no_se_pide_o_no_hay_ia(db_session):
    for ia, usar in ((_IA(disponible=True), False), (_IA(disponible=False), True)):
        r = inf.generar_narrativa(db_session, _informe(), usar_ia=usar, ia=ia)
        assert r["generado_con"] == "reglas" and ia.recibido is None
        assert r["recomendaciones"] == _informe()["recomendaciones_reglas"]


def test_generar_narrativa_con_ia_valida_la_respuesta(db_session):
    ia = _IA({"resumen": "  Buena noche.  ", "recomendaciones": [" Reforzar puerta ", "", "  ", "Comprar hielo"] + [f"r{i}" for i in range(10)]})
    r = inf.generar_narrativa(db_session, _informe(), usar_ia=True, ia=ia)
    assert r["generado_con"] == "IA (modelo-falso)" and r["resumen"] == "Buena noche."
    assert r["recomendaciones"][:2] == ["Reforzar puerta", "Comprar hielo"] and len(r["recomendaciones"]) == 6  # tope de 6, sin vacías
    assert "recomendaciones_reglas" not in ia.recibido["mensajes"][0]["content"].split("Recomendaciones por reglas")[0]  # los datos van sin duplicar las reglas
    largo = inf.generar_narrativa(db_session, _informe(), usar_ia=True, ia=_IA({"resumen": "x" * 3000, "recomendaciones": ["a"]}))
    assert len(largo["resumen"]) == 1500


@pytest.mark.parametrize("respuesta", [{}, {"resumen": "ok", "recomendaciones": []}, {"resumen": "  ", "recomendaciones": ["a"]}, {"resumen": "ok", "recomendaciones": None}])
def test_generar_narrativa_descarta_respuestas_inutilizables(db_session, respuesta):
    r = inf.generar_narrativa(db_session, _informe(), usar_ia=True, ia=_IA(respuesta))
    assert r["generado_con"] == "reglas" and "no entregó un informe utilizable" in r["aviso_ia"]


def test_generar_narrativa_si_la_ia_falla_conserva_el_plan_b(db_session):
    r = inf.generar_narrativa(db_session, _informe(), usar_ia=True, ia=_IA(falla=IANoDisponible("cuota agotada")))
    assert r["generado_con"] == "reglas" and r["aviso_ia"] == "cuota agotada" and r["resumen"]


def test_informe_integrado_con_comisiones_reservas_cortesias_y_conversaciones(client, auth, crear_evento, crear_usuario, monkeypatch):
    monkeypatch.setattr("app.api.v1.reservas_router.notificar_confirmacion_reserva", lambda d: ("enviada", None, "w"))
    monkeypatch.setattr("app.api.v1.reservas_router.notificar_nueva_reserva", lambda d: None)
    evento = crear_evento(aforo=10)
    pro = crear_usuario("pro@nightlife.io", "Promotor")
    puerta = crear_usuario("puerta@nightlife.io", "Puerta")
    for estado, monto in (("liquidada", 700), (None, 300)):
        cid = client.post(f"{API}/comisiones", json={"promotor_id": pro["id"], "evento_id": evento["id"], "porcentaje": 10}, headers=auth).json()["id"]
        client.put(f"{API}/comisiones/{cid}", json={"monto": monto, **({"estado": estado} if estado else {})}, headers=auth)
    for i in range(5):
        client.post(f"{API}/accesos", json={"evento_id": evento["id"], "tipo": "cortesia_manual", "justificacion": f"vip {i}", "nombre_cortesia": f"V{i}"}, headers=puerta["headers"])
    rid = client.post(f"{API}/reservas", json={"evento_id": evento["id"], "nombre_cliente": "Ana", "telefono": "3001234567", "tipo": "mesa", "asistentes": 2}).json()["id"]
    client.patch(f"{API}/reservas/{rid}/estado", json={"estado": "confirmada"}, headers=auth)
    client.post(f"{API}/reservas", json={"evento_id": evento["id"], "nombre_cliente": "Beto", "telefono": "3001234568", "tipo": "palco", "asistentes": 2})
    client.post(f"{API}/chat/mensajes", json={"texto": "Me robaron el celular, una estafa"})
    client.post(f"{API}/inventario", json={"nombre": "Agua", "cantidad": 3, "unidad": "und", "stock_minimo": 5}, headers=auth)

    datos = client.post(f"{API}/dashboard/eventos/{evento['id']}/informe", json={"usar_ia": False}, headers=auth).json()
    assert datos["comisiones"] == {"pendiente": 300.0, "liquidada": 700.0}
    assert datos["puerta"]["cortesias_manuales"] == 5 and datos["puerta"]["validos"] == 5
    assert datos["reservas"] == {"solicitudes": 2, "pendientes": 1, "garantizadas": 1, "canceladas": 0, "pases_emitidos": 2, "pases_usados": 0, "garantizadas_sin_llegada": 1}
    assert datos["sentimiento"]["conversaciones_7d"] == 1 and datos["sentimiento"]["escaladas_abiertas"] == 1
    assert datos["inventario"]["en_minimo"] == ["Agua"]
    recs = " ".join(datos["narrativa"]["recomendaciones"])
    for esperado in ("cortesías manuales", "no llegaron", "pendientes", "nivel mínimo", "comisiones", "escalada"):
        assert esperado in recs
