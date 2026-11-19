from datetime import date

from app.application.risk_engine import RiskEngine
from app.core.config import Settings
from app.domain.enums import NivelAlerta


def _engine() -> RiskEngine:
    return RiskEngine(Settings())


def test_aforo_normal_no_genera_alerta() -> None:
    evaluacion = _engine().evaluar_aforo(
        accesos_validos=50, aforo_maximo=200, fecha_evento=date(2026, 10, 6)  # martes
    )
    assert evaluacion.nivel is None


def test_aforo_alto_genera_alerta_alta() -> None:
    evaluacion = _engine().evaluar_aforo(
        accesos_validos=200, aforo_maximo=200, fecha_evento=date(2026, 10, 6)
    )
    assert evaluacion.nivel == NivelAlerta.ALTO


def test_umbral_se_relaja_en_fin_de_semana() -> None:
    engine = _engine()
    # 170/200 = 85%: en un martes supera el umbral medio (0.85); en sábado
    # el umbral se relaja (+0.05) por la mayor afluencia esperada.
    martes = engine.evaluar_aforo(
        accesos_validos=170, aforo_maximo=200, fecha_evento=date(2026, 10, 6)
    )
    sabado = engine.evaluar_aforo(
        accesos_validos=170, aforo_maximo=200, fecha_evento=date(2026, 10, 10)
    )
    assert martes.nivel == NivelAlerta.MEDIO
    assert sabado.nivel is None


def test_comision_atipica_por_zscore() -> None:
    engine = _engine()
    historico = [100_000.0, 105_000.0, 98_000.0, 102_000.0]
    evaluacion = engine.evaluar_comision_atipica(monto_nuevo=500_000.0, historico=historico)
    assert evaluacion.es_atipica is True
    assert evaluacion.nivel == NivelAlerta.ALTO


def test_comision_normal_no_es_atipica() -> None:
    engine = _engine()
    historico = [100_000.0, 105_000.0, 98_000.0, 102_000.0]
    evaluacion = engine.evaluar_comision_atipica(monto_nuevo=101_000.0, historico=historico)
    assert evaluacion.es_atipica is False


def test_comision_sin_historico_suficiente_no_evalua() -> None:
    engine = _engine()
    evaluacion = engine.evaluar_comision_atipica(monto_nuevo=1_000_000.0, historico=[100_000.0])
    assert evaluacion.es_atipica is False
