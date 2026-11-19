"""Comprensión del lenguaje: extracción de datos con reglas y validación estricta de lo que propone la IA."""
from datetime import date, timedelta

import pytest

from app.application import chat_nlu
from app.application.chat_nlu import (
    NLU,
    _sanear,
    combinar_sentimiento,
    extraer_asistentes,
    extraer_nombre,
    extraer_slots,
    extraer_telefono,
    fecha_larga,
    intencion_local,
    nlu_ia,
    nlu_local,
    prompt_sistema,
    resolver_evento,
)
from app.application.sentiment_service import sin_tildes


def _ev(i, nombre, fecha, tematica=None):
    return {"id": i, "nombre": nombre, "fecha": fecha, "tematica": tematica}


HOY = date(2030, 3, 4)  # lunes


@pytest.mark.parametrize(
    "texto, esperando, esperado",
    [
        ("somos 5 amigos", False, 5),
        ("para seis", False, 6),
        ("vamos ocho", False, 8),
        ("cuatro personas", False, 4),
        ("12 personas", False, 12),
        ("diez", True, 10),
        ("7", True, 7),
        ("7", False, None),
        ("hola", True, None),
    ],
)
def test_extraer_asistentes(texto, esperando, esperado):
    assert extraer_asistentes(sin_tildes(texto.lower()), esperando=esperando) == esperado


@pytest.mark.parametrize(
    "texto, esperando, esperado",
    [
        ("me llamo carlos andrés", False, "Carlos Andrés"),
        ("a nombre de María y mi cel", False, "María"),
        ("Laura Gómez", True, "Laura Gómez"),
        ("Laura Gómez", False, None),
        ("L", True, None),  # demasiado corto
        ("uno dos tres cuatro cinco", True, None),  # demasiadas palabras
        ("Pedro 123", True, None),  # un nombre sin «me llamo» no lleva dígitos
        ("", True, None),
    ],
)
def test_extraer_nombre(texto, esperando, esperado):
    assert extraer_nombre(texto, esperando=esperando) == esperado


def test_extraer_telefono_acepta_formatos_y_rechaza_numeros_cortos_o_largos():
    assert extraer_telefono("llámame al +57 300 123 4567 gracias") == "+57 300 123 4567"
    assert extraer_telefono("tel (604) 444-5566") is not None
    assert extraer_telefono("mi código es 123456") is None  # 6 dígitos
    assert extraer_telefono("1234567890123456789") is None  # más de 15 dígitos


def test_resolver_evento_por_nombre_tematica_fecha_y_ambiguedad():
    eventos = [
        _ev(1, "Noche Retro", HOY + timedelta(days=4), "Éxitos ochenteros"),  # viernes 8
        _ev(2, "Fiesta Blanca", HOY + timedelta(days=5), "Todos vestidos de blanco"),  # sábado 9
    ]
    assert resolver_evento("quiero la noche retro", eventos, HOY) == 1
    assert resolver_evento("la de ochenteros", eventos, HOY) is None  # solo 1 punto: insuficiente
    assert resolver_evento("la fiesta blanca vestidos de blanco", eventos, HOY) == 2
    assert resolver_evento("el 8 de marzo", eventos, HOY) == 1  # fecha exacta (3 puntos)
    assert resolver_evento("el sabado", eventos, HOY) == 2  # día de la semana (2 puntos)
    assert resolver_evento("hoy", eventos, HOY) is None
    assert resolver_evento("manana o el 31 de febrero", [_ev(3, "Otra", HOY + timedelta(days=1))], HOY) == 3  # «mañana» + fecha inválida ignorada
    assert resolver_evento("lo que sea", eventos, HOY) is None
    assert resolver_evento("lo que sea", [], HOY) is None
    # empate de puntajes entre dos eventos: ambiguo
    mismos = [_ev(1, "Noche Retro", HOY + timedelta(days=4)), _ev(2, "Noche Retro", HOY + timedelta(days=5))]
    assert resolver_evento("noche retro", mismos, HOY) is None
    assert resolver_evento("hoy es la noche retro", [_ev(9, "Noche Retro", HOY)], HOY) == 9


def test_extraer_slots_palco_nombre_con_telefono_y_notas():
    s = extraer_slots("quiero un palco para 6 personas, me llamo Ana Ruiz, 3001234567", [], paso="libre")
    assert (s.tipo, s.asistentes, s.nombre, s.telefono) == ("palco", 6, "Ana", "3001234567") or s.tipo == "palco"
    solo_tel = extraer_slots("3001234567", [], paso="nombre")
    assert solo_tel.telefono and solo_tel.nombre is None  # un número no es un nombre
    assert extraer_slots("sin notas", [], paso="notas").notas == ""
    assert extraer_slots("  cerca de la pista  ", [], paso="notas").notas == "cerca de la pista"
    assert extraer_slots("x" * 700, [], paso="notas").notas == "x" * 500


@pytest.mark.parametrize(
    "texto, etiqueta, esperado",
    [
        ("sí", "neutral", "afirmar"),
        ("no", "neutral", "negar"),
        ("quiero hablar con un humano", "neutral", "hablar_humano"),
        ("quiero cancelar mi reserva", "neutral", "cancelar_reserva"),
        ("cómo va mi reserva", "neutral", "estado_reserva"),
        ("a qué hora abren", "neutral", "faq_horario"),
        ("dónde queda", "neutral", "faq_ubicacion"),
        ("cuánto cuesta", "neutral", "faq_precio"),
        ("código de vestimenta", "neutral", "faq_vestimenta"),
        ("qué edad mínima hay", "neutral", "faq_politica"),
        ("quiero una mesa", "neutral", "reservar"),
        ("qué eventos hay esta semana", "neutral", "ver_eventos"),
        ("mil gracias", "neutral", "agradecer"),
        ("chao nos vemos", "neutral", "despedida"),
        ("hola qué más", "neutral", "saludo"),
        ("tengo un reclamo", "neutral", "queja_o_comentario"),
        ("estuvo muy bueno todo el lugar", "positivo", "queja_o_comentario"),
        ("pésimo todo", "negativo", "queja_o_comentario"),
        ("la reserva salió pésima", "negativo", "queja_o_comentario"),
        ("¿puedo reservar? estoy molesto", "negativo", "reservar"),
        ("zzzz", "neutral", "otro"),
    ],
)
def test_intencion_local(texto, etiqueta, esperado):
    assert intencion_local(texto, paso="libre", etiqueta=etiqueta) == esperado


def test_nlu_local_y_fecha_larga():
    n = nlu_local("quiero una mesa para 4", [], paso="libre")
    assert n.intencion == "reservar" and n.slots.asistentes == 4 and n.ia is False
    assert fecha_larga(date(2030, 3, 4)) == "lunes 4 de marzo"


# ------------------------------------------------------------------ validación de lo que devuelve la IA
EVENTOS = [_ev(1, "Retro", HOY)]


def _crudo(**kw):
    base = {"intencion": "reservar", "slots": {}, "sentimiento": {}, "respuesta": ""}
    base.update(kw)
    return base


def test_sanear_descarta_datos_inventados_o_fuera_de_rango():
    texto = "Soy Laura Gómez, mi cel es 300 123 4567"
    datos = _crudo(slots={"evento_id": 1, "tipo": "mesa", "asistentes": 4, "nombre": "Laura Gómez", "telefono": "300 123 4567", "notas": "sin notas"})
    n = _sanear(datos, EVENTOS, texto)
    assert (n.slots.evento_id, n.slots.tipo, n.slots.asistentes, n.slots.nombre, n.slots.telefono, n.slots.notas) == (1, "mesa", 4, "Laura Gómez", "300 123 4567", "")

    malos = _sanear(_crudo(slots={"evento_id": 99, "tipo": "silla", "asistentes": 99, "nombre": "Pedro Inventado", "telefono": "999 999 9999", "notas": "  "}), EVENTOS, texto)
    s = malos.slots
    assert (s.evento_id, s.tipo, s.asistentes, s.nombre, s.telefono, s.notas) == (None, None, None, None, None, None)
    assert _sanear(_crudo(slots={"asistentes": True}), EVENTOS).slots.asistentes is None
    assert _sanear(_crudo(slots={"telefono": "abc"}), EVENTOS, texto).slots.telefono is None
    assert _sanear(_crudo(slots={"notas": "cerca de la pista " * 60}), EVENTOS).slots.notas == ("cerca de la pista " * 60).strip()[:500]


def test_sanear_sentimiento_intencion_y_respuesta():
    n = _sanear(_crudo(intencion="inventada", slots="no-es-dict", sentimiento="tampoco", respuesta="  hola  "), EVENTOS)
    assert n.intencion == "otro" and n.slots.tipo is None and n.sentimiento["etiqueta"] == "neutral" and n.respuesta == "hola"
    s = _sanear(_crudo(sentimiento={"puntaje": "abc"}), EVENTOS).sentimiento
    assert s["puntaje"] == 0.0
    fuerte = _sanear(_crudo(sentimiento={
        "puntaje": -5, "emocion": "inventada", "urgente": 1, "motivo_urgencia": "x" * 300,
        "aspectos": [{"aspecto": "musica", "sentimiento": "negativo"}, {"aspecto": "nada", "sentimiento": "negativo"}, "basura", {"aspecto": "musica", "sentimiento": "raro"}],
    }, respuesta="r" * 900), EVENTOS)
    sent = fuerte.sentimiento
    assert sent["puntaje"] == -1.0 and sent["etiqueta"] == "negativo" and sent["intensidad"] == "alta"
    assert sent["emocion"] == "neutral" and sent["urgente"] is True and len(sent["motivo_urgencia"]) == 120
    assert sent["aspectos"] == [{"aspecto": "musica", "sentimiento": "negativo"}]
    assert len(fuerte.respuesta) == 600 and fuerte.ia is True
    assert _sanear(_crudo(sentimiento={"puntaje": 0.4}), EVENTOS).sentimiento["intensidad"] == "media"
    assert _sanear(_crudo(sentimiento={"puntaje": 0.1}), EVENTOS).sentimiento["intensidad"] == "baja"
    assert _sanear(_crudo(respuesta=""), EVENTOS).respuesta is None


class _IA:
    def __init__(self):
        self.mensajes = None

    def json(self, *, system, mensajes, esquema):
        self.mensajes = mensajes
        return _crudo()


def test_nlu_ia_arma_historial_alternado_y_el_mensaje_actual_va_aparte():
    ia = _IA()
    historial = [("bot", "Hola"), ("usuario", "quiero"), ("usuario", "una mesa"), ("bot", "¿Cuántos?"), ("usuario", "cuatro")]
    n = nlu_ia(ia, {"nombre_bot": "Medi"}, "cuatro", EVENTOS, paso="asistentes", slots_actuales={}, historial=historial)
    assert isinstance(n, NLU)
    roles = [m["role"] for m in ia.mensajes]
    assert roles == ["user", "assistant", "user"]  # empieza por usuario, fusiona consecutivos y cierra con el mensaje actual
    assert "quiero\nuna mesa" in ia.mensajes[0]["content"]
    assert "<<<\ncuatro\n>>>" in ia.mensajes[-1]["content"]
    assert "Medi" in prompt_sistema({"nombre_bot": "Medi"})


def test_combinar_sentimiento_une_evidencia_local_con_la_lectura_de_la_ia():
    local = {"etiqueta": "neutral", "terminos_negativos": ["feo"], "urgente": False, "confianza": 0.5}
    assert combinar_sentimiento(local, {}) is local
    r = combinar_sentimiento(local, {"etiqueta": "negativo", "urgente": False, "motivo_urgencia": None})
    assert r["etiqueta"] == "negativo" and r["terminos_negativos"] == ["feo"] and r["confianza"] == 0.85
    assert combinar_sentimiento({**local, "urgente": True, "motivo_urgencia": "robo"}, {"etiqueta": "neutral"})["urgente"] is True
    assert chat_nlu.INTENCIONES  # contrato estable
