"""Cliente de IA (límite diario, configuración real, respaldo Groq) y motor de sentimiento: comportamiento relativo
de los modificadores (intensificadores, negaciones, contrastes, énfasis)."""
import time
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.application import ia_client
from app.application.ia_client import ClienteIA, IANoDisponible, LimiteDiario
from app.application.sentiment_service import analizar_sentimiento
from app.core.config import Settings

ESQUEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
MENSAJES = [{"role": "user", "content": "hola"}]


# ------------------------------------------------------------------ IA
def test_limite_diario_se_reinicia_al_cambiar_de_dia(monkeypatch):
    lim = LimiteDiario()
    assert lim.consumir(2) and lim.consumir(2) and not lim.consumir(2)
    assert lim.usadas == 2

    class Manana(date):
        @classmethod
        def today(cls):
            return date.today() + timedelta(days=1)

    monkeypatch.setattr(ia_client, "date", Manana)
    assert lim.usadas == 0  # el contador de ayer ya no cuenta
    assert lim.consumir(2) and lim.usadas == 1


def test_configuracion_real_distingue_gemini_groq_y_nada(monkeypatch):
    monkeypatch.undo()  # el conftest apaga «configurada» para todas las pruebas; aquí se evalúa la propiedad real
    solo_gemini = ClienteIA(Settings(gemini_api_key="k1", gemini_api_keys_extra="k2, ,k1", groq_api_key="", _env_file=None))
    assert solo_gemini.configurada and solo_gemini.claves_configuradas == 2 and not solo_gemini.con_groq and solo_gemini.disponible
    solo_groq = ClienteIA(Settings(gemini_api_key="", groq_api_key=" gsk ", _env_file=None))
    assert solo_groq.configurada and solo_groq.con_groq and solo_groq.claves_configuradas == 0
    nada = ClienteIA(Settings(gemini_api_key="", groq_api_key="", _env_file=None))
    assert not nada.configurada and not nada.disponible
    apagada = ClienteIA(Settings(gemini_api_key="k", _env_file=None), habilitada=False)
    assert apagada.configurada and not apagada.disponible
    with pytest.raises(IANoDisponible):
        nada.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)


def test_cliente_gemini_se_crea_una_sola_vez_por_clave_sin_red(monkeypatch):
    monkeypatch.undo()
    ia = ClienteIA(Settings(gemini_api_key="k1", gemini_api_keys_extra="k2", _env_file=None))
    primero = ia._sdk(0)
    assert ia._sdk(0) is primero and ia._sdk(1) is not primero  # un cliente por clave, reutilizado


def _ia_groq(monkeypatch, respuestas):
    monkeypatch.setattr(ClienteIA, "configurada", property(lambda self: True))
    monkeypatch.setattr(ia_client, "_limite", ia_client.LimiteDiario())
    monkeypatch.setattr(ia_client, "_enfriados", {})
    ia = ClienteIA(Settings(gemini_api_key="", groq_api_key="gsk", groq_model="g1", groq_model_respaldo="g2", _env_file=None))
    enviados = []

    def post(url, *, headers, json, timeout):
        enviados.append(json["model"])
        return respuestas.pop(0)

    monkeypatch.setattr(ia_client.httpx, "post", post)
    return ia, enviados


class _Http:
    def __init__(self, codigo, cuerpo=None, cabeceras=None):
        self.status_code, self._cuerpo, self.headers = codigo, cuerpo or {}, cabeceras or {}

    def json(self):
        return self._cuerpo


def test_groq_modelo_en_pausa_se_salta_y_si_todos_estan_en_pausa_falla(monkeypatch):
    ia, enviados = _ia_groq(monkeypatch, [_Http(200, {"choices": [{"message": {"content": '{"ok": true}'}}]})])
    ia_client._enfriados["groq:g1"] = time.monotonic() + 100
    assert ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA) == {"ok": True}
    assert enviados == ["g2"]  # g1 estaba en pausa

    ia_client._enfriados["groq:g2"] = time.monotonic() + 100
    with pytest.raises(IANoDisponible, match="pausa temporal"):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert enviados == ["g2"]  # no se molestó al proveedor


def test_groq_pausa_por_defecto_si_retry_after_no_es_numerico_y_error_no_reintentable(monkeypatch):
    ia, enviados = _ia_groq(monkeypatch, [_Http(429, cabeceras={"retry-after": "pronto"}), _Http(503)])
    with pytest.raises(IANoDisponible, match="HTTP 503"):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert enviados == ["g1", "g2"]
    assert ia_client._enfriados["groq:g1"] > time.monotonic()  # se enfrió con la pausa por defecto del código 429

    ia2, enviados2 = _ia_groq(monkeypatch, [_Http(422)])
    with pytest.raises(IANoDisponible, match="HTTP 422"):
        ia2.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert enviados2 == ["g1"]  # una solicitud rechazada no se reintenta con otro modelo


def test_gemini_rechazo_distinto_de_cuota_no_prueba_otros_modelos(monkeypatch):
    monkeypatch.setattr(ClienteIA, "configurada", property(lambda self: True))
    monkeypatch.setattr(ia_client, "_limite", ia_client.LimiteDiario())
    monkeypatch.setattr(ia_client, "_enfriados", {})
    ia = ClienteIA(Settings(gemini_api_key="k", gemini_model="m1", gemini_model_respaldo="m2", _env_file=None))
    llamados = []

    def generar(*, model, contents, config):
        llamados.append(model)
        raise errors.APIError(422, {"error": {"message": "x"}})

    ia._clientes[0] = SimpleNamespace(models=SimpleNamespace(generate_content=generar))
    with pytest.raises(IANoDisponible, match="HTTP 422"):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert llamados == ["m1"]


# ------------------------------------------------------------------ sentimiento
def _p(texto):
    return analizar_sentimiento(texto)["puntaje"]


def test_los_modificadores_cambian_la_intensidad_en_la_direccion_esperada():
    assert _p("muy amable") > _p("amable") > 0  # intensificador
    assert _p("algo caro") > _p("caro")  # atenuador: «algo caro» es menos grave
    assert _p("poco amable") < 0 < _p("amable")  # «poco» invierte lo positivo
    assert _p("no es amable") < 0  # negación
    assert _p("no es caro") > _p("caro")  # negar lo negativo lo suaviza
    assert _p("PÉSIMO servicio") < _p("pésimo servicio")  # mayúsculas sostenidas = énfasis
    assert _p("horrible!!") < _p("horrible")  # exclamaciones repetidas = énfasis
    assert _p("☕") == 0


def test_emojis_cuentan_con_tope_y_definen_la_emocion():
    uno, muchos = analizar_sentimiento("😍"), analizar_sentimiento("😍😍😍😍😍😍")
    assert uno["etiqueta"] == muchos["etiqueta"] == "positivo" and uno["emocion"] == "alegria"
    assert muchos["puntaje"] >= uno["puntaje"]
    enojo = analizar_sentimiento("😡")
    assert enojo["etiqueta"] == "negativo" and enojo["emocion"] == "enojo"


def test_el_contraste_da_mas_peso_a_lo_que_viene_despues():
    assert _p("el lugar es bueno pero muy caro") < 0 < _p("muy caro pero el lugar es bueno")
    assert _p("estuvo bueno aunque tardaron mucho") < _p("tardaron mucho aunque estuvo bueno")


def test_texto_vacio_es_neutral_y_no_falla():
    r = analizar_sentimiento("   ")
    assert r["etiqueta"] == "neutral" and r["puntaje"] == 0 and r["urgente"] is False


def test_urgencia_por_palabra_y_por_frase():
    assert analizar_sentimiento("me robaron el celular")["urgente"] is True
    r = analizar_sentimiento("me hicieron un cobro indebido en la cuenta")
    assert r["urgente"] is True and r["motivo_urgencia"]
    assert analizar_sentimiento("la música estuvo genial")["urgente"] is False
