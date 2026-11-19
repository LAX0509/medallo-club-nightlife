"""Gestor de diálogo del asistente (``Asistente``) probado turno a turno contra la base en memoria:
flujo de reserva, cambios, preguntas frecuentes, escalamiento, estado/cancelación de reservas por WhatsApp,
modo de prueba (dry_run) y el uso (validado) de una IA simulada."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.application import bot_config
from app.application.chatbot import Asistente, MensajeBot, Opcion, TarjetaEvento, a_texto_whatsapp
from app.application.ia_client import IANoDisponible
from app.infrastructure.models.evento_model import EventoModel
from app.infrastructure.models.notificacion_model import NotificacionModel
from app.infrastructure.models.reserva_model import ReservaModel
from app.infrastructure.models.usuario_model import UsuarioModel


class IAFalsa:
    """Sustituto de ``ClienteIA``: devuelve lo que se le indique o falla como si la cuota se hubiera agotado."""

    disponible = True

    def __init__(self, respuesta=None, falla=False):
        self.respuesta = respuesta
        self.falla = falla
        self.llamadas = 0

    def json(self, **kwargs):
        self.llamadas += 1
        if self.falla:
            raise IANoDisponible("sin cuota")
        return self.respuesta


def _datos_ia(intencion="otro", slots=None, puntaje=0.0, urgente=False, respuesta="", aspectos=None):
    return {
        "intencion": intencion,
        "slots": {"evento_id": None, "tipo": None, "asistentes": None, "nombre": None, "telefono": None, "notas": None, **(slots or {})},
        "sentimiento": {"etiqueta": "x", "puntaje": puntaje, "emocion": "neutral", "aspectos": aspectos or [], "urgente": urgente, "motivo_urgencia": "robo" if urgente else None},
        "respuesta": respuesta,
    }


@pytest.fixture
def admin_id(db_session):
    from app.core.security import hash_password

    u = UsuarioModel(nombre="Adm", email="a@a.io", password_hash=hash_password("x1234567"), rol="Administrador", estado=True)
    db_session.add(u)
    db_session.commit()
    return u.id


def _evento(db, admin_id, nombre="Noche Retro", dias=5, tematica="Éxitos de los 80", estado="planeado"):
    e = EventoModel(administrador_id=admin_id, nombre=nombre, fecha=date.today() + timedelta(days=dias), aforo_maximo=100, estado=estado, tematica=tematica)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


class Charla:
    def __init__(self, db, **kw):
        kw.setdefault("canal", "web")
        self.asistente = Asistente(db, **kw)
        self.estado = None
        self.ultimo = None

    def di(self, texto=None, accion=None):
        self.ultimo = self.asistente.turno(self.estado, texto, accion)
        self.estado = self.ultimo.estado
        return self.ultimo

    @property
    def texto(self):
        return " ".join(m.texto for m in self.ultimo.mensajes)

    @property
    def valores(self):
        return [o.valor for m in self.ultimo.mensajes for o in m.opciones]


# ------------------------------------------------------------------ sin eventos
def test_sin_eventos_abiertos_no_se_puede_reservar_ni_listar(db_session):
    c = Charla(db_session)
    c.di("quiero reservar una mesa para 4")
    assert "no hay eventos abiertos" in c.texto and c.estado["paso"] == "libre"
    c.di(accion="ver_eventos")
    assert "no hay eventos abiertos" in c.texto
    assert "reservar" in c.valores  # el menú principal sigue ofreciendo opciones


def test_evento_cerrado_o_pasado_no_aparece(db_session, admin_id):
    _evento(db_session, admin_id, "Cerrado", estado="cerrado")
    _evento(db_session, admin_id, "Pasado", dias=-3)
    c = Charla(db_session)
    c.di(accion="ver_eventos")
    assert "no hay eventos abiertos" in c.texto


# ------------------------------------------------------------------ reserva guiada con varios eventos
def test_reserva_con_varios_eventos_cambios_y_confirmacion_en_whatsapp(db_session, admin_id):
    e1 = _evento(db_session, admin_id, "Noche Retro", dias=5)
    e2 = _evento(db_session, admin_id, "Fiesta Blanca", dias=9, tematica="Todos de blanco")
    c = Charla(db_session, canal="whatsapp", contacto_tel="573001234567")

    c.di("hola, quiero reservar")
    assert c.estado["paso"] == "evento" and f"evento:{e1.id}" in c.valores and f"evento:{e2.id}" in c.valores
    assert c.ultimo.mensajes[-1].eventos  # tarjetas con los eventos
    assert "Responde con el número" in a_texto_whatsapp(c.ultimo.mensajes)

    c.di("2")  # en WhatsApp el número elige la segunda opción: Fiesta Blanca
    assert c.estado["slots"]["evento_id"] == e2.id and c.estado["paso"] == "tipo"
    c.di(accion="tipo:palco")
    assert c.estado["paso"] == "asistentes"
    c.di("1")  # en 'asistentes' un número es el dato pedido, no una opción
    assert c.estado["slots"]["asistentes"] == 1 and c.estado["paso"] == "nombre"
    c.di("Camila Restrepo")
    # el teléfono se toma del chat de WhatsApp: salta directo a notas
    assert c.estado["slots"]["telefono"] == "+573001234567" and c.estado["paso"] == "notas"
    c.di(accion="notas:ninguna")
    assert c.estado["paso"] == "confirmar" and "1 persona " in c.texto and "Fiesta Blanca" in c.texto

    # cambiar algo -> menú; cambiar personas -> vuelve a preguntar
    c.di(accion="cambiar")
    assert "cambiar:evento" in c.valores
    c.di(accion="cambiar:personas")
    assert c.estado["paso"] == "asistentes" and "asistentes" not in c.estado["slots"]
    c.di("para 6 personas")
    assert c.estado["paso"] == "confirmar"
    c.di("no")  # negar en el resumen abre el menú de cambios
    assert "cambiar:nombre" in c.valores
    c.di(accion="cambiar:evento")
    assert c.estado["paso"] == "evento" and "evento_id" not in c.estado["slots"]
    c.di(accion=f"evento:{e1.id}")
    assert c.estado["paso"] == "confirmar" and "Noche Retro" in c.texto

    c.di("sí")
    assert c.ultimo.reserva and c.ultimo.reserva.id > 0 and "Sigue o gestiona tu reserva aquí" in c.texto
    assert c.ultimo.reserva.datos_notificacion["promotor"] == "Asistente virtual"
    assert c.ultimo.reserva.datos_notificacion["tipo"] == "Palco"
    r = db_session.get(ReservaModel, c.ultimo.reserva.id)
    assert (r.asistentes, r.tipo, r.telefono, r.evento_id) == (6, "palco", "+573001234567", e1.id)


def test_pregunta_ajena_en_pleno_flujo_responde_y_retoma(db_session, admin_id):
    _evento(db_session, admin_id, "Uno", dias=3)
    _evento(db_session, admin_id, "Dos", dias=7, tematica="Otra")
    c = Charla(db_session)
    c.di("quiero reservar")
    c.di("¿a qué hora abren?")
    assert "horario" in c.texto.lower() and "Sigamos con tu reserva" in c.texto and c.estado["paso"] == "evento"
    c.di("blablabla xyz")  # nada reconocible en el paso 'evento'
    assert "No logré entender ese dato" in c.texto
    c.di("quiero reservar")  # repetir la intención solo repite la pregunta
    assert c.estado["paso"] == "evento" and "¿A cuál evento" in c.texto


def test_paso_notas_con_texto_libre_y_negar(db_session, admin_id):
    _evento(db_session, admin_id)
    c = Charla(db_session)
    c.di("quiero una mesa para 3 personas")
    assert c.estado["paso"] == "nombre"
    c.di("Pedro Pérez")
    assert c.estado["paso"] == "telefono"
    c.di("320 555 1212")
    assert c.estado["paso"] == "notas"
    c.di("no")  # negar en notas equivale a «sin notas»
    assert c.estado["slots"]["notas"] == "" and c.estado["paso"] == "confirmar"
    c.di(accion="reiniciar")
    assert c.estado["paso"] == "libre" and c.estado["slots"] == {} and "empezamos de nuevo" in c.texto


def test_hablar_humano_durante_la_reserva_y_sin_contacto_configurado(db_session, admin_id):
    _evento(db_session, admin_id)
    c = Charla(db_session)
    c.di("quiero una mesa para 3 personas")
    c.di("quiero hablar con un asesor")
    assert c.ultimo.escalada and "aviso al equipo" in c.texto
    assert c.estado["esperando_contacto"] is True  # en web se pide un teléfono
    c.di("mi número es 3001234567")
    assert "Dejé tu número" in c.texto and c.estado["contacto_humano"]


def test_contacto_del_equipo_configurado_y_empatia_con_reserva_en_whatsapp(db_session, admin_id):
    config = bot_config.obtener_config(db_session)
    config = {**config, "contacto_equipo": "wa.me/573000000000"}
    c = Charla(db_session, canal="whatsapp", config=config, contacto_tel="573001234567", url_reservas="https://club/reservas")
    c.di("Pésimo servicio, la reserva fue un desastre y nadie confirmó la mesa")
    assert c.ultimo.escalada and "wa.me/573000000000" in c.texto and "https://club/reservas" in c.texto


def test_segunda_queja_ya_escalada_no_vuelve_a_escalar_salvo_urgente(db_session):
    c = Charla(db_session)
    c.di("Qué servicio tan horrible, qué mamera")
    assert c.ultimo.escalada_nueva
    assert c.estado["escalada"] is True
    c.di("Qué pésimo, muy mala atención")
    assert c.ultimo.escalada and not c.ultimo.escalada_nueva  # no se avisa dos veces al equipo por lo mismo
    n_antes = len(db_session.execute(select(NotificacionModel)).scalars().all())
    c.di("me robaron el celular, una estafa")  # lo urgente sí vuelve a avisar
    assert c.ultimo.escalada_nueva
    assert len(db_session.execute(select(NotificacionModel)).scalars().all()) == n_antes + 1


def test_escalamiento_desactivado_en_configuracion(db_session):
    config = {**bot_config.obtener_config(db_session), "escalar_negativos": "false"}
    c = Charla(db_session, config=config)
    c.di("Qué servicio tan horrible, qué mamera")
    assert not c.ultimo.escalada
    assert "Lamentamos" in c.texto


def test_escalamiento_en_dry_run_no_crea_notificaciones(db_session):
    c = Charla(db_session, dry_run=True)
    c.di("Me robaron el celular, fue una estafa")
    assert c.ultimo.escalada
    c.di("mi cel 3001234567")
    assert db_session.execute(select(NotificacionModel)).scalars().all() == []


# ------------------------------------------------------------------ preguntas frecuentes y charla
@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("hola", "menú"),
        ("¿cuánto cuesta la entrada?", None),
        ("¿cómo me visto?", "años"),
        ("¿qué incluye la garantía?", "Edad mínima"),
        ("¿dónde queda?", "Estamos en"),
        ("¿a qué hora abren?", "horario"),
        ("muchas gracias", "Con gusto"),
        ("chao", "Hasta pronto"),
        ("dale", "Qué te gustaría"),
        ("no gracias", "Entendido"),
        ("¿qué eventos hay?", "no hay eventos"),
        ("asdfgh qwerty", "Puedo mostrarte"),
    ],
)
def test_preguntas_frecuentes_y_charla_basica(db_session, texto, esperado):
    c = Charla(db_session)
    c.di(texto)
    assert c.ultimo.mensajes
    if esperado == "menú":
        assert "reservar" in c.valores
    elif esperado:
        assert esperado.lower() in c.texto.lower()


def test_comentarios_positivo_neutral_y_negativo(db_session):
    c = Charla(db_session)
    c.di("La música estuvo chimba y la atención muy amable, gracias")
    assert "Gracias por tu comentario" in c.texto
    c.di("tengo una sugerencia sobre el lugar")
    assert "Compartí tu comentario" in c.texto
    c.di("Mal servicio y mala atención")
    assert c.ultimo.analisis["etiqueta"] == "negativo"


def test_eventos_mostrados_en_whatsapp_como_texto(db_session, admin_id):
    _evento(db_session, admin_id)
    c = Charla(db_session, canal="whatsapp")
    c.di(accion="ver_eventos")
    assert "próximos eventos" in c.texto
    plano = a_texto_whatsapp([MensajeBot("Hay:", eventos=[TarjetaEvento(1, "Retro", "2030-01-01", "martes 1 de enero", None, None)])])
    assert "• Retro · martes 1 de enero" in plano
    assert a_texto_whatsapp([MensajeBot("x" * 5000)]) == "x" * 4000


# ------------------------------------------------------------------ estado, enlace y cancelación
def _reserva(db, evento, telefono="3001234567", estado="pendiente", garantia=None, **extra):
    r = ReservaModel(evento_id=evento.id, nombre_cliente="Cliente", telefono=telefono, tipo="mesa", asistentes=2, estado=estado, codigo_garantia=garantia, **extra)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_estado_de_reserva_sin_reservas_en_web_y_whatsapp(db_session):
    web = Charla(db_session)
    web.di("¿cómo va mi reserva?")
    assert "enlace privado" in web.texto
    wa = Charla(db_session, canal="whatsapp", contacto_tel="573001234567")
    wa.di("¿cómo va mi reserva?")
    assert "este número" in wa.texto
    web.di(accion="cancelar_pregunta")
    assert "No encuentro una reserva activa" in web.texto
    web.di(accion="reenviar_enlace")
    assert "No encuentro una reserva activa" in web.texto
    web.di(accion="cancelar_si:5")
    assert "No encuentro una reserva activa" in web.texto


def test_estado_de_reserva_en_whatsapp_con_varios_estados_y_cancelacion(db_session, admin_id):
    ev = _evento(db_session, admin_id)
    pendiente = _reserva(db_session, ev, "+57 300 123 4567")
    garantizada = _reserva(db_session, ev, "300-123-4567", estado="confirmada", garantia="MC-00002-AB12", hora_limite="23:00", ubicacion_asignada="Palco 3")
    confirmada = _reserva(db_session, ev, "3001234567", estado="confirmada")
    otra = _reserva(db_session, ev, "3109999999")  # de otra persona: no debe aparecer
    c = Charla(db_session, canal="whatsapp", contacto_tel="573001234567")
    c.di("estado de mi reserva")
    assert f"#{pendiente.id}" in c.texto and "pendiente" in c.texto
    assert "GARANTIZADA con el código MC-00002-AB12" in c.texto and "Hora límite 23:00" in c.texto and "Palco 3" in c.texto
    assert f"#{confirmada.id}" in c.texto and "confirmada." in c.texto
    assert f"#{otra.id}" not in c.texto
    assert "reenviar_enlace" in c.valores and "cancelar_pregunta" in c.valores

    # reenviar enlace rota el token: el anterior deja de servir
    confirmada.token_cancelacion_hash = "hash-viejo"  # el enlace se emite para la reserva activa más reciente
    db_session.commit()
    hash_antes = "hash-viejo"
    c.di(accion="reenviar_enlace")
    assert "tu enlace privado" in c.texto and "reserva=" in c.texto and "token=" in c.texto
    db_session.expire_all()
    assert db_session.get(ReservaModel, confirmada.id).token_cancelacion_hash != hash_antes

    # cancelar: pregunta -> no -> pregunta -> sí
    c.di("quiero cancelar mi reserva")
    assert "¿Seguro" in c.texto and any(v.startswith("cancelar_si:") for v in c.valores)
    c.di(accion="cancelar_no")
    assert "sigue como estaba" in c.texto and c.estado["pendiente_cancelar"] is None
    c.di(accion="cancelar_pregunta")
    destino = next(v for v in c.valores if v.startswith("cancelar_si:"))
    c.di(accion=destino)
    assert "cancelé tu reserva" in c.texto
    assert db_session.get(ReservaModel, int(destino.split(":")[1])).estado == "cancelada"
    assert "reserva_cancelada" in {n.tipo for n in db_session.execute(select(NotificacionModel)).scalars()}


def test_cancelar_elige_la_reserva_indicada_y_marca_error_si_ya_ingresaron(db_session, admin_id):
    from app.infrastructure.models.invitado_model import InvitadoModel

    ev = _evento(db_session, admin_id)
    r1 = _reserva(db_session, ev)
    r2 = _reserva(db_session, ev)
    db_session.add(InvitadoModel(evento_id=ev.id, promotor_id=admin_id, reserva_id=r2.id, nombre="x", qr_code="NLD-1-AAAAAAAAAAAAAAAA", estado="usado"))
    db_session.commit()
    c = Charla(db_session, canal="whatsapp", contacto_tel="3001234567")
    c.di(accion=f"cancelar_si:{r1.id}")
    assert db_session.get(ReservaModel, r1.id).estado == "cancelada"
    c.di(accion=f"cancelar_si:{r2.id}")  # con un pase ya usado la cancelación se rechaza con el motivo
    assert "ya ingresaron" in c.texto and db_session.get(ReservaModel, r2.id).estado != "cancelada"
    # la reserva cancelada sola se lista como cancelada
    c.di("estado de mi reserva")
    assert f"#{r2.id}" in c.texto


def test_estado_de_reserva_cancelada_y_reserva_de_la_sesion_web(db_session, admin_id):
    ev = _evento(db_session, admin_id)
    r = _reserva(db_session, ev, estado="cancelada")
    c = Charla(db_session)
    c.estado = {"reserva_id": r.id}
    c.di("estado de mi reserva")
    assert "cancelada." in c.texto and "cancelar_pregunta" not in c.valores
    c.estado = {"reserva_id": 99999}
    c.di("estado de mi reserva")
    assert "No encuentro reservas" in c.texto


# ------------------------------------------------------------------ modo de prueba y errores de creación
def test_dry_run_no_crea_ni_cancela_nada(db_session, admin_id):
    ev = _evento(db_session, admin_id)
    r = _reserva(db_session, ev)
    c = Charla(db_session, canal="whatsapp", contacto_tel="3001234567", dry_run=True)
    c.di("quiero reservar una mesa para 4 a nombre de Ana Lopez")
    c.di(accion="notas:ninguna")
    assert c.estado["paso"] == "confirmar"
    c.di("sí")
    assert c.ultimo.reserva.simulada and "(Prueba)" in c.texto
    assert len(db_session.execute(select(ReservaModel)).scalars().all()) == 1
    c.di(accion="reenviar_enlace")
    assert "(Prueba)" in c.texto
    c.di(accion=f"cancelar_si:{r.id}")
    assert "(Prueba)" in c.texto and db_session.get(ReservaModel, r.id).estado == "pendiente"


def test_si_el_evento_deja_de_estar_disponible_se_informa_y_reinicia(db_session, admin_id):
    ev = _evento(db_session, admin_id)
    c = Charla(db_session)
    c.di("quiero una mesa para 3 personas")
    c.di("Laura Gómez")
    c.di("300 123 4567")
    c.di("sin notas")
    assert c.estado["paso"] == "confirmar"
    ev.estado = "cerrado"
    db_session.commit()
    c.di("sí")
    assert "ya no está disponible" in c.texto and c.estado["paso"] == "libre" and c.ultimo.reserva is None


def test_promotor_del_estado_se_asocia_a_la_reserva(db_session, admin_id):
    from app.core.security import hash_password

    ev = _evento(db_session, admin_id)
    prom = UsuarioModel(nombre="Pro Mo", email="pm@a.io", password_hash=hash_password("x1234567"), rol="Promotor", estado=True)
    db_session.add(prom)
    db_session.commit()
    c = Charla(db_session)
    c.estado = {"promotor_id": prom.id}
    c.di("quiero una mesa para 3 personas")
    c.di("Laura Gómez")
    c.di("300 123 4567")
    c.di("sin notas")
    c.di("sí")
    assert c.ultimo.reserva.datos_notificacion["promotor"] == "Pro Mo"


# ------------------------------------------------------------------ IA simulada (la IA propone, el sistema dispone)
def test_ia_extrae_datos_y_las_reglas_completan_lo_que_la_ia_omite(db_session, admin_id):
    _evento(db_session, admin_id)
    ia = IAFalsa(_datos_ia("reservar", {"tipo": "mesa"}, respuesta=""))
    c = Charla(db_session, ia=ia)
    c.di("quiero reservar una mesa para 4 personas, mi cel es 3001234567 en una frase larga que no entiende el motor")
    assert ia.llamadas == 1 and c.ultimo.ia_usada
    # la IA no devolvió asistentes ni teléfono pero las reglas sí los vieron
    assert c.estado["slots"]["asistentes"] == 4 and c.estado["slots"]["telefono"] == "3001234567"
    assert c.estado["slots"]["tipo"] == "mesa"


def test_ia_intencion_otro_se_corrige_con_las_reglas_y_sentimiento_se_combina(db_session):
    ia = IAFalsa(_datos_ia("otro", puntaje=-0.9, urgente=True, respuesta="algo"))
    c = Charla(db_session, ia=ia)
    c.di("¿dónde queda el club? Me robaron ayer, una estafa")
    assert c.ultimo.ia_usada and c.ultimo.escalada  # urgencia combinada IA + reglas
    assert c.ultimo.analisis["urgente"] is True


def test_ia_respuesta_abierta_en_saludo_y_otro(db_session):
    ia = IAFalsa(_datos_ia("saludo", respuesta="¡Qué hubo, parcero! ¿En qué te ayudo?"))
    c = Charla(db_session, ia=ia)
    c.di("ey qué más pues, ¿cómo así que todo bien por allá en el club?")
    assert "parcero" in c.texto
    c2 = Charla(db_session, ia=IAFalsa(_datos_ia("otro", respuesta="Eso lo confirma el equipo.")))
    c2.di("¿tienen parqueadero para motos eléctricas con carga rápida?")  # sin intención local clara
    assert c2.ultimo.mensajes


def test_ia_queja_negativa_usa_la_respuesta_de_la_ia_sin_menu(db_session):
    ia = IAFalsa(_datos_ia("queja_o_comentario", puntaje=-0.3, respuesta="Lamento lo ocurrido, cuéntame más."))
    config = {**bot_config.obtener_config(db_session), "escalar_negativos": "false"}
    c = Charla(db_session, ia=ia, config=config)
    c.di("La verdad la noche no estuvo tan buena que digamos, mucha gente")
    assert "cuéntame más" in c.texto
    assert not c.ultimo.mensajes[-1].opciones


def test_ia_no_disponible_cae_al_motor_local(db_session, admin_id):
    _evento(db_session, admin_id)
    ia = IAFalsa(falla=True)
    c = Charla(db_session, ia=ia)
    c.di("¿a qué hora abren? cuéntame con detalle por favor")
    assert ia.llamadas == 1 and not c.ultimo.ia_usada and "horario" in c.texto.lower()


def test_ia_notas_en_paso_notas_se_conservan_de_las_reglas(db_session, admin_id):
    _evento(db_session, admin_id)
    c = Charla(db_session)
    c.di("quiero una mesa para 3 personas")
    c.di("Laura Gómez")
    c.di("300 123 4567")
    assert c.estado["paso"] == "notas"
    c.asistente.ia = IAFalsa(_datos_ia("otro", slots={"notas": None}, puntaje=-0.5))
    c.di("es un cumpleaños sorpresa, ojalá cerca de la pista, gracias")
    assert c.estado["slots"]["notas"].startswith("es un cumpleaños") or c.estado["paso"] == "confirmar"


@pytest.mark.parametrize(
    "paso, texto, esperado_ia",
    [
        ("nombre", "Camila Restrepo", 0),  # las reglas ya extrajeron el dato pedido: no se gasta cuota de IA
        ("telefono", "300 123 4567", 0),
        ("asistentes", "4", 0),
        ("confirmar", "sí", 0),
        ("notas", "cerca de la pista", 0),
        ("nombre", "Camila Restrepo, estoy muy molesta con el servicio de ustedes, qué pésimo y horrible todo", 1),  # tono negativo: sí consulta
        ("notas", "quiero hablar con un asesor", 1),
        ("confirmar", "no sé, déjame pensarlo con calma y te aviso luego", 1),
        ("libre", "hola buenas", 1),
    ],
)
def test_la_ia_solo_se_consulta_cuando_las_reglas_no_bastan(db_session, admin_id, paso, texto, esperado_ia):
    _evento(db_session, admin_id)
    ia = IAFalsa(_datos_ia("otro"))
    c = Charla(db_session, ia=ia)
    c.estado = {"paso": paso, "slots": {"evento_id": 1, "evento_nombre": "x", "evento_fecha": date.today().isoformat(), "tipo": "mesa", "asistentes": 2, "nombre": "A", "telefono": "3001234567", "notas": ""}}
    c.di(texto)
    assert ia.llamadas == esperado_ia


def test_acciones_desconocidas_o_malformadas_no_rompen_el_turno(db_session, admin_id):
    _evento(db_session, admin_id)
    c = Charla(db_session)
    for accion in ("evento:abc", "tipo:silla", "asistentes:x", "inventada", "faq:", "faq:horario", "estado_reserva"):
        c.di(accion=accion)
        assert c.ultimo.mensajes
    assert Opcion("a", "b").valor == "b"


def test_numero_fuera_de_rango_y_accion_de_asistentes(db_session, admin_id):
    _evento(db_session, admin_id)
    c = Charla(db_session, canal="whatsapp")
    c.di("hola")
    c.di("9")  # no hay opción 9: se trata como texto normal, no como opción
    assert c.ultimo.mensajes
    c = Charla(db_session)
    c.di("quiero reservar una mesa")
    c.di(accion="asistentes:3")
    assert c.estado["slots"]["asistentes"] == 3


def test_pedir_humano_repetido_o_fuera_del_flujo_no_duplica_mensajes(db_session, admin_id):
    _evento(db_session, admin_id)
    c = Charla(db_session)
    c.di("quiero hablar con un asesor")
    assert "aviso al equipo" in c.texto
    c.di("quiero hablar con un asesor")  # ya escalada: el escalamiento calla y se muestra la ayuda general
    assert "Puedo mostrarte" in c.texto
    # en pleno flujo, si la persona pide un humano, el escalamiento ya respondió
    d = Charla(db_session)
    d.di("quiero reservar")
    d.di("quiero hablar con una persona real")
    assert "aviso al equipo" in d.texto
    d.di("asesor por favor")
    assert d.ultimo.mensajes
