"""Arranque y configuración de infraestructura: selección del pool de conexiones según el entorno, carpeta de
subidas de solo lectura, sesión por petición y casos límite de utilidades."""
import base64
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy

from app.application import inventario_service
from app.application.ia_client import ClienteIA, IANoDisponible
from app.application.qr_format import leer_qr
from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError
from app.infrastructure.database import session as modulo_sesion
from app.infrastructure.models.inventario_item_model import InventarioItemModel

RAIZ = Path(__file__).resolve().parents[1] / "app"


def _ejecutar_modulo(ruta: Path, nombre: str) -> dict:
    """Ejecuta el código REAL del módulo en un espacio de nombres aislado (sin tocar el módulo ya importado,
    cuya ``Base`` y ``app`` usan el resto de las pruebas)."""
    espacio = {"__name__": nombre, "__file__": str(ruta)}
    exec(compile(ruta.read_text(encoding="utf-8"), str(ruta), "exec"), espacio)
    return espacio


def _pool_para(monkeypatch, *, url: str, serverless: str | None):
    capturado = {}
    crear_real = sqlalchemy.create_engine

    def _crear(url_bd, **kw):
        capturado.update(url=url_bd, **kw)
        return crear_real("sqlite+pysqlite:///:memory:")

    for var in ("VERCEL", "AWS_LAMBDA_FUNCTION_NAME", "NOTIFICACIONES_EN_LINEA"):
        monkeypatch.delenv(var, raising=False)
    if serverless:
        monkeypatch.setenv("NOTIFICACIONES_EN_LINEA", serverless)
    monkeypatch.setattr(sqlalchemy, "create_engine", _crear)
    monkeypatch.setattr(get_settings(), "database_url", url)
    _ejecutar_modulo(RAIZ / "infrastructure" / "database" / "session.py", "app.infrastructure.database.session_copia")
    return capturado


def test_pool_de_conexiones_segun_el_entorno(monkeypatch):
    pg = _pool_para(monkeypatch, url="postgresql+psycopg://u:p@host/db", serverless=None)
    assert pg["pool_size"] == 10 and pg["max_overflow"] == 30 and pg["pool_pre_ping"] is True
    local = _pool_para(monkeypatch, url="sqlite:///./x.db", serverless=None)
    assert "pool_size" not in local and "poolclass" not in local
    sin_servidor = _pool_para(monkeypatch, url="postgresql+psycopg://u:p@host/db", serverless="true")
    assert sin_servidor["poolclass"] is sqlalchemy.pool.NullPool and "pool_size" not in sin_servidor


def test_get_db_entrega_una_sesion_y_la_cierra():
    generador = modulo_sesion.get_db()
    db = next(generador)
    assert db.get_bind() is modulo_sesion.engine
    cerrada = []
    db.close = lambda: cerrada.append(True)
    with pytest.raises(StopIteration):
        next(generador)
    assert cerrada == [True]


def test_si_la_carpeta_de_subidas_es_de_solo_lectura_la_app_arranca_igual(monkeypatch):
    def _sin_permiso(self, *a, **kw):
        raise OSError("sistema de archivos de solo lectura")

    monkeypatch.setattr(Path, "mkdir", _sin_permiso)
    espacio = _ejecutar_modulo(RAIZ / "main.py", "app.main_copia")
    from fastapi.testclient import TestClient

    cliente = TestClient(espacio["app"])
    assert cliente.get("/health").json() == {"status": "ok"}  # el arranque no falló por la carpeta de solo lectura


# ------------------------------------------------------------------ utilidades
def test_gemini_sin_el_sdk_instalado_se_informa_sin_romper(monkeypatch):
    ia = ClienteIA(Settings(gemini_api_key="k", _env_file=None))
    monkeypatch.setitem(sys.modules, "google.genai", None)  # simula «pip uninstall google-genai»
    with pytest.raises(IANoDisponible, match="google-genai"):
        ia._json_gemini("s", [{"role": "user", "content": "hola"}], {"type": "object"}, 100)


def test_qr_en_base64_que_no_decodifica_se_rechaza_sin_excepciones_inesperadas():
    invalido = "A" * 25  # parece base64 pero su longitud es imposible (1 más que múltiplo de 4)
    with pytest.raises(ValueError, match="no reconocido"):
        leer_qr(invalido)
    valido = base64.urlsafe_b64encode(b"NLD-3-ABCDEFGHIJKLMNOP").decode()
    assert leer_qr(valido).codigo == "NLD-3-ABCDEFGHIJKLMNOP" and leer_qr(valido).formato == "base64"


def test_movimiento_de_inventario_con_tipo_desconocido_se_rechaza(db_session):
    item = InventarioItemModel(nombre="Agua", categoria="B", cantidad=Decimal("5"), unidad="und", stock_minimo=Decimal("1"))
    db_session.add(item)
    db_session.commit()
    with pytest.raises(ConflictError, match="Tipo de movimiento no válido"):
        inventario_service.registrar_movimiento(db_session, item, tipo="regalo", cantidad=Decimal("1"))
    assert item.cantidad == Decimal("5")  # no se tocó el stock


def test_qr_con_llaves_pero_json_roto_no_se_interpreta_como_json():
    with pytest.raises(ValueError, match="no reconocido"):
        leer_qr("{esto no es json")
    # aun roto, si contiene un código NLD reconocible dentro de un texto, se rescata como «texto»
    assert leer_qr("{roto NLD-3-ABCDEFGHIJKLMNOP roto").formato == "texto"
