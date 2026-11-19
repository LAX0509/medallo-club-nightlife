"""Cliente de IA (Gemini): contrato, respaldo entre modelos y manejo de errores, sin red."""

from types import SimpleNamespace

import pytest
from google.genai import errors

from app.application import chat_nlu, ia_client
from app.application.ia_client import ClienteIA, IANoDisponible
from app.core.config import Settings

ESQUEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
MENSAJES = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "¡Hola!"}]


class ModelosFalsos:
    """Simula ``client.models`` : cada modelo responde con un valor o lanza una excepción."""

    def __init__(self, guion: dict):
        self.guion = guion
        self.llamadas: list[str] = []
        self.ultimo_config = None
        self.ultimos_contenidos = None

    def generate_content(self, *, model, contents, config):
        self.llamadas.append(model)
        self.ultimo_config, self.ultimos_contenidos = config, contents
        resultado = self.guion[model]
        if isinstance(resultado, Exception):
            raise resultado
        return SimpleNamespace(text=resultado)


def _ia(monkeypatch, guion: dict, *, limite: int = 1000) -> tuple[ClienteIA, ModelosFalsos]:
    monkeypatch.setattr(ClienteIA, "configurada", property(lambda self: True))
    monkeypatch.setattr(ia_client, "_limite", ia_client.LimiteDiario())
    monkeypatch.setattr(ia_client, "_enfriados", {})
    ajustes = Settings(
        gemini_api_key="clave-de-prueba", gemini_model="m1", gemini_model_respaldo="m2,m3", _env_file=None
    )
    ia = ClienteIA(ajustes, limite_diario=limite)
    modelos = ModelosFalsos(guion)
    ia._clientes[0] = SimpleNamespace(models=modelos)
    return ia, modelos


def _error(codigo: int) -> errors.APIError:
    return errors.APIError(codigo, {"error": {"message": "x"}})


def test_respuesta_json_y_contrato_del_request(monkeypatch):
    ia, modelos = _ia(monkeypatch, {"m1": '{"ok": true}'})
    assert ia.json(system="sistema", mensajes=MENSAJES, esquema=ESQUEMA) == {"ok": True}
    assert modelos.llamadas == ["m1"]
    assert modelos.ultimo_config.response_mime_type == "application/json"
    assert modelos.ultimo_config.system_instruction == "sistema"
    # el rol «assistant» se traduce al «model» de Gemini
    assert [c.role for c in modelos.ultimos_contenidos] == ["user", "model"]
    assert ia.modelo == "m1"


@pytest.mark.parametrize("codigo", [404, 429, 503])
def test_cae_al_modelo_de_respaldo(monkeypatch, codigo):
    ia, modelos = _ia(monkeypatch, {"m1": _error(codigo), "m2": '{"ok": true}'})
    assert ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA) == {"ok": True}
    assert modelos.llamadas == ["m1", "m2"]
    assert ia.modelo == "m2"


def test_todos_los_modelos_agotados(monkeypatch):
    ia, modelos = _ia(monkeypatch, {"m1": _error(429), "m2": _error(429), "m3": _error(503)})
    with pytest.raises(IANoDisponible):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert modelos.llamadas == ["m1", "m2", "m3"]


@pytest.mark.parametrize("codigo", [401, 403])
def test_clave_invalida_no_prueba_otros_modelos(monkeypatch, codigo):
    ia, modelos = _ia(monkeypatch, {"m1": _error(codigo), "m2": '{"ok": true}'})
    with pytest.raises(IANoDisponible):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert modelos.llamadas == ["m1"]


@pytest.mark.parametrize("texto", ["", "   ", "no es json", "[1, 2]", '"texto"'])
def test_respuesta_vacia_o_invalida(monkeypatch, texto):
    ia, _ = _ia(monkeypatch, {"m1": texto, "m2": texto, "m3": texto})
    with pytest.raises(IANoDisponible):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)


def test_error_de_red_se_traduce(monkeypatch):
    ia, _ = _ia(monkeypatch, {"m1": TimeoutError("sin red")})
    with pytest.raises(IANoDisponible):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)


def test_limite_diario(monkeypatch):
    ia, _ = _ia(monkeypatch, {"m1": '{"ok": true}'}, limite=2)
    ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    with pytest.raises(IANoDisponible, match="límite diario"):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert ia_client.llamadas_ia_hoy() == 2


def test_sin_clave_no_disponible():
    ia = ClienteIA(Settings(gemini_api_key="", _env_file=None))
    assert not ia.configurada and not ia.disponible
    with pytest.raises(IANoDisponible):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)


def _sin_anyof(nodo) -> bool:
    if isinstance(nodo, dict):
        return "anyOf" not in nodo and all(_sin_anyof(v) for v in nodo.values())
    if isinstance(nodo, list):
        return all(_sin_anyof(v) for v in nodo)
    return True


def test_esquema_del_nlu_usa_nulos_compatibles_con_gemini():
    assert _sin_anyof(chat_nlu._ESQUEMA)
    tipo = chat_nlu._ESQUEMA["properties"]["slots"]["properties"]["tipo"]
    assert tipo["type"] == ["string", "null"] and None in tipo["enum"]
    assert chat_nlu._ESQUEMA["properties"]["slots"]["properties"]["asistentes"]["type"] == ["integer", "null"]


def _datos_ia(**slots):
    base = {"evento_id": None, "tipo": None, "asistentes": None, "nombre": None, "telefono": None, "notas": None}
    base.update(slots)
    return {"intencion": "reservar", "slots": base, "sentimiento": {"puntaje": 0}, "respuesta": ""}


def test_nombre_alterado_por_la_ia_se_descarta():
    # La IA devolvió «Laura G3gmez» aunque el cliente escribió «Laura Gómez»: no es confiable.
    nlu = chat_nlu._sanear(_datos_ia(nombre="Laura G3gmez"), [], "me llamo Laura Gómez")
    assert nlu.slots.nombre is None
    nlu = chat_nlu._sanear(_datos_ia(nombre="Laura Gómez"), [], "me llamo Laura Gómez")
    assert nlu.slots.nombre == "Laura Gómez"


def test_telefono_inventado_por_la_ia_se_descarta():
    assert chat_nlu._sanear(_datos_ia(telefono="3009998877"), [], "mi cel es 3001234567").slots.telefono is None
    assert chat_nlu._sanear(_datos_ia(telefono="300 123 4567"), [], "mi cel es 3001234567").slots.telefono == "300 123 4567"


@pytest.mark.parametrize("texto", ["ninguna nota", "Sin notas", "no", "nada", "ninguna", "no, gracias"])
def test_sin_notas_no_se_guarda_como_nota(texto):
    assert chat_nlu.extraer_slots(texto, [], paso="notas").notas == ""
    assert chat_nlu._sanear(_datos_ia(notas=texto), [], texto).slots.notas == ""


def test_nota_real_se_conserva():
    assert chat_nlu.extraer_slots("es un cumpleaños, mesa cerca a la pista", [], paso="notas").notas.startswith("es un cumple")


def test_modelo_con_cuota_agotada_se_enfria_y_no_se_vuelve_a_llamar(monkeypatch):
    ia, modelos = _ia(monkeypatch, {"m1": _error(429), "m2": '{"ok": true}', "m3": '{"ok": true}'})
    ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert modelos.llamadas == ["m1", "m2", "m2"]  # la segunda consulta omite m1 (en pausa)


def test_todos_en_pausa_falla_sin_llamar_al_proveedor(monkeypatch):
    ia, modelos = _ia(monkeypatch, {"m1": _error(429), "m2": _error(429), "m3": _error(503)})
    with pytest.raises(IANoDisponible):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    llamadas = len(modelos.llamadas)
    with pytest.raises(IANoDisponible, match="pausa"):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert len(modelos.llamadas) == llamadas


def test_tope_total_de_tiempo_corta_la_cadena_de_respaldos(monkeypatch):
    ia, modelos = _ia(monkeypatch, {"m1": _error(503), "m2": '{"ok": true}'})
    reloj = iter([0.0, 0.0, 0.0, 50.0, 50.0, 50.0, 50.0])  # el segundo intento ya pasó el presupuesto de 12 s
    monkeypatch.setattr(ia_client.time, "monotonic", lambda: next(reloj, 50.0))
    with pytest.raises(IANoDisponible, match="demasiado"):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert modelos.llamadas == ["m1"]


def test_pausa_sugerida_por_google():
    e = errors.APIError(429, {"error": {"message": "Quota exceeded. Please retry in 15h13m51.26s."}})
    assert ia_client._pausa_sugerida(e) == 6 * 3600  # 15 h pedidas: se limita a 6 h
    corta = errors.APIError(429, {"error": {"message": "Please retry in 12.5s"}})
    assert ia_client._pausa_sugerida(corta) == 30.0  # nunca menos de 30 s
    assert ia_client._pausa_sugerida(errors.APIError(429, {"error": {"message": "sin dato"}})) is None


def test_cuota_diaria_agotada_pausa_el_modelo_horas(monkeypatch):
    msg = {"error": {"message": "limit: 20, model: m1. Please retry in 15h13m51s."}}
    ia, modelos = _ia(monkeypatch, {"m1": errors.APIError(429, msg), "m2": '{"ok": true}'})
    ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert ia_client._enfriados["m1#0"] - ia_client.time.monotonic() > 3600


def test_error_400_de_un_modelo_prueba_el_siguiente(monkeypatch):
    ia, modelos = _ia(monkeypatch, {"m1": _error(400), "m2": '{"ok": true}'})
    assert ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA) == {"ok": True}
    assert modelos.llamadas == ["m1", "m2"]


def test_modelo_que_no_admite_el_nivel_de_razonamiento_se_reintenta_sin_el(monkeypatch):
    rechazo = errors.APIError(400, {"error": {"message": "Thinking level MINIMAL is not supported for this model."}})
    ia, modelos = _ia(monkeypatch, {"m1": rechazo})
    llamadas = []

    def generar(*, model, contents, config):
        llamadas.append(config.thinking_config)
        if len(llamadas) == 1:
            raise rechazo
        return SimpleNamespace(text='{"ok": true}')

    ia._clientes[0] = SimpleNamespace(models=SimpleNamespace(generate_content=generar))
    assert ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA) == {"ok": True}
    assert llamadas[0] is not None and llamadas[1] is None  # segundo intento sin thinking_config


def _ia_multiclave(monkeypatch, guiones: list[dict]) -> tuple[ClienteIA, list[ModelosFalsos]]:
    monkeypatch.setattr(ClienteIA, "configurada", property(lambda self: bool(self._claves())))  # la real (conftest la apaga)
    monkeypatch.setattr(ia_client, "_limite", ia_client.LimiteDiario())
    monkeypatch.setattr(ia_client, "_enfriados", {})
    ajustes = Settings(
        gemini_api_key="clave-1", gemini_api_keys_extra="clave-2, clave-3 ,clave-1", gemini_model="m1",
        gemini_model_respaldo="m2", _env_file=None,
    )
    ia = ClienteIA(ajustes)
    falsos = [ModelosFalsos(g) for g in guiones]
    for i, f in enumerate(falsos):
        ia._clientes[i] = SimpleNamespace(models=f)
    return ia, falsos


def test_claves_extra_sin_duplicados_ni_vacios(monkeypatch):
    ia, _ = _ia_multiclave(monkeypatch, [{}, {}, {}])
    assert ia.claves_configuradas == 3 and ia.configurada


def test_si_una_clave_agota_su_cuota_responde_la_siguiente_con_el_mismo_modelo(monkeypatch):
    ia, (k1, k2, _) = _ia_multiclave(monkeypatch, [{"m1": _error(429), "m2": _error(429)}, {"m1": '{"ok": true}'}, {}])
    assert ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA) == {"ok": True}
    assert k1.llamadas == ["m1"] and k2.llamadas == ["m1"]  # se prueba la otra clave antes de bajar de modelo
    assert ia.modelo == "m1" and ia._clave_activa == 1


def test_clave_invalida_se_descarta_y_se_usa_la_otra(monkeypatch):
    ia, (k1, k2, _) = _ia_multiclave(monkeypatch, [{"m1": _error(401), "m2": _error(401)}, {"m1": '{"ok": true}'}, {}])
    assert ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA) == {"ok": True}
    ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert k1.llamadas == ["m1"]  # la clave inválida no se vuelve a llamar
    assert len(k2.llamadas) == 2


def test_todas_las_claves_agotadas(monkeypatch):
    todo = {"m1": _error(429), "m2": _error(429)}
    ia, falsos = _ia_multiclave(monkeypatch, [todo, todo, todo])
    with pytest.raises(IANoDisponible):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert sum(len(f.llamadas) for f in falsos) == 6  # 2 modelos x 3 claves


class RespuestaHttp:
    def __init__(self, codigo: int, cuerpo: dict | None = None, cabeceras: dict | None = None):
        self.status_code, self._cuerpo, self.headers = codigo, cuerpo or {}, cabeceras or {}

    def json(self):
        return self._cuerpo


def _contenido(texto: str) -> dict:
    return {"choices": [{"message": {"content": texto}}]}


def _ia_groq(monkeypatch, respuestas: list, *, gemini: bool = True):
    monkeypatch.setattr(ClienteIA, "configurada", property(lambda self: bool(self._claves()) or bool(self._clave_groq())))
    monkeypatch.setattr(ia_client, "_limite", ia_client.LimiteDiario())
    monkeypatch.setattr(ia_client, "_enfriados", {})
    ajustes = Settings(
        gemini_api_key="clave-1" if gemini else "", gemini_model="m1", gemini_model_respaldo="",
        groq_api_key="gsk-prueba", groq_model="g1", groq_model_respaldo="g2", _env_file=None,
    )
    ia = ClienteIA(ajustes)
    modelos = ModelosFalsos({"m1": _error(429)})
    ia._clientes[0] = SimpleNamespace(models=modelos)
    enviados = []

    def post(url, *, headers, json, timeout):
        enviados.append((url, json["model"], headers["Authorization"], json["response_format"]))
        r = respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(ia_client.httpx, "post", post)
    return ia, enviados


def test_si_gemini_falla_responde_groq(monkeypatch):
    ia, enviados = _ia_groq(monkeypatch, [RespuestaHttp(200, _contenido('{"ok": true}'))])
    assert ia.json(system="sistema", mensajes=MENSAJES, esquema=ESQUEMA) == {"ok": True}
    assert enviados == [("https://api.groq.com/openai/v1/chat/completions", "g1", "Bearer gsk-prueba", {"type": "json_object"})]
    assert ia.modelo == "g1"


def test_groq_pasa_al_modelo_de_respaldo_si_hay_limite(monkeypatch):
    ia, enviados = _ia_groq(monkeypatch, [RespuestaHttp(429, cabeceras={"retry-after": "30"}), RespuestaHttp(200, _contenido('{"ok": true}'))])
    assert ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA) == {"ok": True}
    assert [e[1] for e in enviados] == ["g1", "g2"]


def test_groq_clave_invalida_no_prueba_mas(monkeypatch):
    ia, enviados = _ia_groq(monkeypatch, [RespuestaHttp(401)])
    with pytest.raises(IANoDisponible):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    assert len(enviados) == 1


def test_groq_respuesta_invalida_o_red_caida(monkeypatch):
    ia, _ = _ia_groq(monkeypatch, [RespuestaHttp(200, _contenido("no es json")), RespuestaHttp(200, _contenido("[1]"))])
    with pytest.raises(IANoDisponible):
        ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)
    ia2, _ = _ia_groq(monkeypatch, [ia_client.httpx.ConnectError("sin red")])
    with pytest.raises(IANoDisponible):
        ia2.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA)


def test_solo_groq_sin_claves_de_gemini(monkeypatch):
    ia, enviados = _ia_groq(monkeypatch, [RespuestaHttp(200, _contenido('{"ok": true}'))], gemini=False)
    assert ia.configurada and ia.claves_configuradas == 0
    assert ia.json(system="s", mensajes=MENSAJES, esquema=ESQUEMA) == {"ok": True}
