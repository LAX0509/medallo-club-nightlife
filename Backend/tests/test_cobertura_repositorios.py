"""Pruebas directas de repositorios y servicios de acceso: ramas de error, concurrencia simulada y
bloqueo por evento de PostgreSQL (con un motor simulado, sin base real)."""
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pytest

from app.application.acceso_service import AccesoService
from app.application.risk_engine import RiskEngine
from app.application.usuario_service import UsuarioService
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.acceso_qr import AccesoQR
from app.domain.entities.alerta_riesgo import AlertaRiesgo
from app.domain.entities.comision import Comision
from app.domain.entities.evento import Evento
from app.domain.entities.invitado import Invitado
from app.domain.entities.usuario import Usuario
from app.domain.enums import (
    EstadoInvitado,
    NivelAlerta,
    ResultadoAcceso,
    RolUsuario,
    TipoAcceso,
    TipoAlerta,
)
from app.infrastructure.repositories.sqlalchemy_acceso_qr_repository import (
    _BASE_CLAVE_BLOQUEO,
    SqlAlchemyAccesoQRRepository,
)
from app.infrastructure.repositories.sqlalchemy_alerta_riesgo_repository import SqlAlchemyAlertaRiesgoRepository
from app.infrastructure.repositories.sqlalchemy_comision_repository import SqlAlchemyComisionRepository
from app.infrastructure.repositories.sqlalchemy_evento_repository import SqlAlchemyEventoRepository
from app.infrastructure.repositories.sqlalchemy_invitado_repository import SqlAlchemyInvitadoRepository
from app.infrastructure.repositories.sqlalchemy_usuario_repository import SqlAlchemyUsuarioRepository


@pytest.fixture
def repos(db_session):
    return {
        "usuarios": SqlAlchemyUsuarioRepository(db_session),
        "eventos": SqlAlchemyEventoRepository(db_session),
        "invitados": SqlAlchemyInvitadoRepository(db_session),
        "accesos": SqlAlchemyAccesoQRRepository(db_session),
        "alertas": SqlAlchemyAlertaRiesgoRepository(db_session),
        "comisiones": SqlAlchemyComisionRepository(db_session),
    }


@pytest.fixture
def base(repos):
    promotor = repos["usuarios"].crear(Usuario(id=None, nombre="P", email="p@x.io", password_hash="h", rol=RolUsuario.PROMOTOR))
    evento = repos["eventos"].crear(Evento(id=None, administrador_id=promotor.id, nombre="E", fecha=date(2030, 1, 1), aforo_maximo=2))
    return promotor, evento


def test_actualizar_sobre_registros_inexistentes_falla_con_valueerror(repos):
    fantasma_u = Usuario(id=999, nombre="x", email="x@x.io", password_hash="h", rol=RolUsuario.PUERTA)
    with pytest.raises(ValueError, match="Usuario 999"):
        repos["usuarios"].actualizar(fantasma_u)
    with pytest.raises(ValueError, match="Evento 999"):
        repos["eventos"].actualizar(Evento(id=999, administrador_id=1, nombre="x", fecha=date.today(), aforo_maximo=1))
    with pytest.raises(ValueError, match="Invitado 999"):
        repos["invitados"].actualizar(Invitado(id=999, evento_id=1, promotor_id=1, nombre="x", qr_code="q"))
    with pytest.raises(ValueError, match="Acceso 999"):
        repos["accesos"].actualizar(AccesoQR(id=999, evento_id=1, invitado_id=None, tipo=TipoAcceso.QR, resultado=ResultadoAcceso.VALIDO))
    with pytest.raises(ValueError, match="Alerta 999"):
        repos["alertas"].actualizar(AlertaRiesgo(id=999, evento_id=1, tipo_alerta=TipoAlerta.SOBREAFORO, nivel=NivelAlerta.BAJO, descripcion="d"))
    with pytest.raises(ValueError, match="Comisión 999"):
        repos["comisiones"].actualizar(Comision(id=999, promotor_id=1, evento_id=1, porcentaje=Decimal("5")))


def test_invitado_repo_actualizar_marcar_usado_contar_y_eliminar(repos, base):
    promotor, evento = base
    inv = repos["invitados"].crear(Invitado(id=None, evento_id=evento.id, promotor_id=promotor.id, nombre="A", qr_code="NLD-1-AAAAAAAAAAAAAAAA"))
    assert inv.esta_disponible and inv.estado == EstadoInvitado.PENDIENTE
    inv.nombre = "A2"
    assert repos["invitados"].actualizar(inv).nombre == "A2"
    assert repos["invitados"].obtener_por_qr("NLD-1-AAAAAAAAAAAAAAAA").id == inv.id
    assert repos["invitados"].obtener_por_qr("otro") is None
    assert repos["invitados"].contar_por_evento_y_promotor(evento.id, promotor.id) == 0
    assert repos["invitados"].marcar_usado_si_pendiente(inv.id) is True
    assert repos["invitados"].marcar_usado_si_pendiente(inv.id) is False  # ya usado: no se reusa
    usado = repos["invitados"].obtener_por_id(inv.id)
    assert usado.estado == EstadoInvitado.USADO and not usado.esta_disponible
    assert repos["invitados"].contar_por_evento_y_promotor(evento.id, promotor.id) == 1
    repos["invitados"].eliminar(inv.id)
    repos["invitados"].eliminar(inv.id)  # idempotente
    assert repos["invitados"].obtener_por_id(inv.id) is None


def test_acceso_repo_actualizar_eliminar_y_contar(repos, base):
    _, evento = base
    a = repos["accesos"].crear(AccesoQR(id=None, evento_id=evento.id, invitado_id=None, tipo=TipoAcceso.CORTESIA_MANUAL, resultado=ResultadoAcceso.VALIDO, justificacion="vip"))
    a.resultado = ResultadoAcceso.RECHAZADO
    a.justificacion = "anulado"
    act = repos["accesos"].actualizar(a)
    assert (act.resultado, act.justificacion) == (ResultadoAcceso.RECHAZADO, "anulado")
    assert repos["accesos"].contar_por_evento_y_resultado(evento.id, ResultadoAcceso.RECHAZADO) == 1
    assert repos["accesos"].contar_por_evento_y_resultado(evento.id, ResultadoAcceso.VALIDO) == 0
    repos["accesos"].eliminar(a.id)
    repos["accesos"].eliminar(a.id)  # idempotente
    assert repos["accesos"].obtener_por_id(a.id) is None


def test_bloqueo_por_evento_en_sqlite_no_hace_nada(repos, base):
    _, evento = base
    with repos["accesos"].bloquear_evento(evento.id):
        pass


def test_bloqueo_por_evento_en_postgresql_toma_y_libera_el_advisory_lock():
    """Con un motor simulado de PostgreSQL se verifica el protocolo lock -> trabajo -> unlock, incluso si el trabajo falla."""
    llamadas = []

    class Conexion:
        def execute(self, sentencia, parametros):
            llamadas.append((str(sentencia), parametros))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            llamadas.append(("cerrar", None))

    class Dialecto:
        name = "postgresql"

    class Motor:
        dialect = Dialecto()

        def connect(self):
            return Conexion()

    class Sesion:
        def get_bind(self):
            return Motor()

    repo = SqlAlchemyAccesoQRRepository(Sesion())
    with repo.bloquear_evento(7):
        llamadas.append(("trabajo", None))
    assert [c[0] for c in llamadas] == ["SELECT pg_advisory_lock(:clave)", "trabajo", "SELECT pg_advisory_unlock(:clave)", "cerrar"]
    assert llamadas[0][1] == {"clave": _BASE_CLAVE_BLOQUEO + 7}

    llamadas.clear()
    with pytest.raises(RuntimeError):
        with repo.bloquear_evento(8):
            raise RuntimeError("falló el registro")
    assert "SELECT pg_advisory_unlock(:clave)" in [c[0] for c in llamadas]  # se libera aunque falle


def _servicio_acceso(repos):
    return AccesoService(repos["accesos"], repos["invitados"], repos["eventos"], repos["alertas"], RiskEngine(get_settings()))


def test_qr_valido_con_aforo_lleno_es_rechazado(repos, base):
    promotor, evento = base  # aforo 2
    svc = _servicio_acceso(repos)
    invs = [repos["invitados"].crear(Invitado(id=None, evento_id=evento.id, promotor_id=promotor.id, nombre=f"I{i}", qr_code=f"NLD-1-{i:016d}")) for i in range(3)]
    assert [svc.registrar_acceso_qr(evento_id=evento.id, qr_code=i.qr_code).acceso.resultado for i in invs] == [
        ResultadoAcceso.VALIDO, ResultadoAcceso.VALIDO, ResultadoAcceso.RECHAZADO]
    # el tercer pase no se consumió: sigue pendiente y podrá entrar si se libera aforo
    assert repos["invitados"].obtener_por_id(invs[2].id).estado == EstadoInvitado.PENDIENTE


def test_carrera_entre_puertas_el_segundo_lector_cuenta_como_duplicado(repos, base, monkeypatch):
    """Otro lector gana el cambio pendiente->usado entre la lectura y la marca: este intento es un reuso."""
    promotor, evento = base
    svc = _servicio_acceso(repos)
    inv = repos["invitados"].crear(Invitado(id=None, evento_id=evento.id, promotor_id=promotor.id, nombre="I", qr_code="NLD-1-CCCCCCCCCCCCCCCC"))
    monkeypatch.setattr(repos["invitados"], "marcar_usado_si_pendiente", lambda _id: False)
    r = svc.registrar_acceso_qr(evento_id=evento.id, qr_code=inv.qr_code)
    assert r.acceso.resultado == ResultadoAcceso.DUPLICADO
    assert r.alertas_generadas and r.alertas_generadas[0].tipo_alerta == TipoAlerta.CORTESIA_DUPLICADA


def test_acceso_service_errores_de_dominio(repos, base):
    _, evento = base
    svc = _servicio_acceso(repos)
    with pytest.raises(NotFoundError):
        svc.registrar_acceso_qr(evento_id=999, qr_code="x")
    with pytest.raises(NotFoundError):
        svc.registrar_cortesia_manual(evento_id=999, justificacion="x")
    with pytest.raises(ValidationError):
        svc.registrar_cortesia_manual(evento_id=evento.id, justificacion="  ")
    with pytest.raises(NotFoundError):
        svc.obtener(999)
    with pytest.raises(NotFoundError):
        svc.anular(999)
    with pytest.raises(NotFoundError):
        svc.eliminar(999)
    # cortesía manual dentro del aforo: 1 de 2 = 50 %
    r = svc.registrar_cortesia_manual(evento_id=evento.id, justificacion="vip")
    assert r.porcentaje_aforo == pytest.approx(0.5)


def test_usuario_service_validar_rol_y_obtener(repos, base):
    promotor, _ = base
    svc = UsuarioService(repos["usuarios"])
    assert svc.validar_rol(promotor.id, RolUsuario.PROMOTOR).id == promotor.id
    with pytest.raises(ValidationError, match="debe tener rol Administrador"):
        svc.validar_rol(promotor.id, RolUsuario.ADMINISTRADOR)
    with pytest.raises(NotFoundError):
        svc.obtener(999)
    # actualizar sin campos no cambia nada
    sin_cambios = svc.actualizar(promotor.id, nombre=None, rol=None, estado=None, telefono=None)
    assert sin_cambios.nombre == "P" and sin_cambios.estado is True
