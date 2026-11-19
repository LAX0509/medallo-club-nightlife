"""Motor de riesgos y alertas (HU004).

Implementa detección de anomalías mediante reglas estadísticas ligeras
(umbrales dinámicos de aforo + z-score sobre el histórico de comisiones),
sin depender de librerías pesadas de ML. La interfaz está aislada en esta
clase para que, en una fase posterior, el cálculo de ``evaluar_*`` pueda
sustituirse por un modelo entrenado (p. ej. scikit-learn) sin tocar el
resto de la aplicación.
"""

from dataclasses import dataclass
from datetime import date
from statistics import mean, pstdev

from app.core.config import Settings
from app.domain.enums import NivelAlerta, TipoAlerta


@dataclass
class EvaluacionAforo:
    nivel: NivelAlerta | None
    descripcion: str | None
    porcentaje_aforo: float


@dataclass
class EvaluacionComision:
    es_atipica: bool
    nivel: NivelAlerta | None
    descripcion: str | None
    z_score: float | None


class RiskEngine:
    """Motor de detección de anomalías de Nightlife Data Scientist."""

    # Los fines de semana (viernes=4, sábado=5) concentran mayor afluencia:
    # se aplica un margen de tolerancia mayor para evitar falsos positivos
    # por picos de ingreso normales en esos días (HU004: "recalcular
    # umbrales según el día de la semana").
    DIAS_ALTA_AFLUENCIA = {4, 5}
    AJUSTE_UMBRAL_ALTA_AFLUENCIA = 0.05

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _umbrales_para_fecha(self, fecha_evento: date) -> tuple[float, float]:
        ajuste = (
            self.AJUSTE_UMBRAL_ALTA_AFLUENCIA
            if fecha_evento.weekday() in self.DIAS_ALTA_AFLUENCIA
            else 0.0
        )
        umbral_medio = min(self._settings.umbral_sobreaforo_medio + ajuste, 0.99)
        umbral_alto = self._settings.umbral_sobreaforo_alto
        return umbral_medio, umbral_alto

    def evaluar_aforo(
        self, *, accesos_validos: int, aforo_maximo: int, fecha_evento: date
    ) -> EvaluacionAforo:
        porcentaje = accesos_validos / aforo_maximo if aforo_maximo else 0.0
        umbral_medio, umbral_alto = self._umbrales_para_fecha(fecha_evento)

        if porcentaje >= umbral_alto:
            return EvaluacionAforo(
                nivel=NivelAlerta.ALTO,
                descripcion=(
                    f"Aforo al {porcentaje:.0%} de la capacidad máxima "
                    f"({accesos_validos}/{aforo_maximo}). Riesgo de sobreaforo."
                ),
                porcentaje_aforo=porcentaje,
            )
        if porcentaje >= umbral_medio:
            return EvaluacionAforo(
                nivel=NivelAlerta.MEDIO,
                descripcion=(
                    f"Aforo acercándose al límite: {porcentaje:.0%} "
                    f"({accesos_validos}/{aforo_maximo})."
                ),
                porcentaje_aforo=porcentaje,
            )
        return EvaluacionAforo(nivel=None, descripcion=None, porcentaje_aforo=porcentaje)

    def evaluar_cortesia_duplicada(self) -> tuple[NivelAlerta, str]:
        return (
            NivelAlerta.ALTO,
            "Se detectó un intento de reingreso con un código QR ya utilizado "
            "(posible duplicación de cortesía).",
        )

    def evaluar_comision_atipica(
        self, *, monto_nuevo: float, historico: list[float]
    ) -> EvaluacionComision:
        """Detecta si una comisión se aleja del comportamiento histórico del promotor.

        Usa z-score sobre el histórico de comisiones liquidadas; requiere al
        menos 3 registros previos para tener significancia estadística.
        """
        if len(historico) < 3:
            return EvaluacionComision(
                es_atipica=False, nivel=None, descripcion=None, z_score=None
            )

        promedio = mean(historico)
        desviacion = pstdev(historico)
        if desviacion == 0:
            return EvaluacionComision(
                es_atipica=False, nivel=None, descripcion=None, z_score=None
            )

        z_score = (monto_nuevo - promedio) / desviacion
        umbral = self._settings.umbral_zscore_comision_atipica

        if abs(z_score) >= umbral:
            nivel = NivelAlerta.ALTO if abs(z_score) >= umbral * 1.5 else NivelAlerta.MEDIO
            descripcion = (
                f"Comisión de {monto_nuevo:,.0f} COP se desvía significativamente "
                f"del histórico del promotor (promedio {promedio:,.0f} COP, "
                f"z-score {z_score:.2f})."
            )
            return EvaluacionComision(
                es_atipica=True, nivel=nivel, descripcion=descripcion, z_score=z_score
            )
        return EvaluacionComision(
            es_atipica=False, nivel=None, descripcion=None, z_score=z_score
        )

    @staticmethod
    def tipo_alerta_para(nombre: str) -> TipoAlerta:
        return TipoAlerta(nombre)
