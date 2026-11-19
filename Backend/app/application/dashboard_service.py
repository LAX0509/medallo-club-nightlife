from dataclasses import dataclass, field

from app.core.exceptions import NotFoundError
from app.domain.entities.alerta_riesgo import AlertaRiesgo
from app.domain.enums import EstadoAlerta, EstadoComision, NivelAlerta, ResultadoAcceso
from app.domain.repositories.acceso_qr_repository import AccesoQRRepository
from app.domain.repositories.alerta_riesgo_repository import AlertaRiesgoRepository
from app.domain.repositories.comision_repository import ComisionRepository
from app.domain.repositories.evento_repository import EventoRepository


@dataclass
class ResumenEvento:
    evento_id: int
    evento_nombre: str
    aforo_maximo: int
    accesos_validos: int
    accesos_duplicados: int
    accesos_rechazados: int
    porcentaje_aforo: float
    comisiones_pendientes: float
    comisiones_liquidadas: float
    alertas_activas: list[AlertaRiesgo] = field(default_factory=list)
    nivel_riesgo_general: str = "bajo"
    recomendacion: str = ""


class DashboardService:
    """Consolida el panel de riesgos y el resumen de cierre de jornada (HU004)."""

    def __init__(
        self,
        evento_repository: EventoRepository,
        acceso_repository: AccesoQRRepository,
        comision_repository: ComisionRepository,
        alerta_repository: AlertaRiesgoRepository,
    ) -> None:
        self._eventos = evento_repository
        self._accesos = acceso_repository
        self._comisiones = comision_repository
        self._alertas = alerta_repository

    def _nivel_general(self, alertas: list[AlertaRiesgo]) -> NivelAlerta:
        if any(a.nivel == NivelAlerta.ALTO for a in alertas):
            return NivelAlerta.ALTO
        if any(a.nivel == NivelAlerta.MEDIO for a in alertas):
            return NivelAlerta.MEDIO
        return NivelAlerta.BAJO

    def _recomendacion(
        self, nivel: NivelAlerta, porcentaje_aforo: float, duplicados: int
    ) -> str:
        if nivel == NivelAlerta.ALTO:
            return (
                "Riesgo alto: revise de inmediato el control de puerta y valide "
                "manualmente las últimas comisiones antes de liquidarlas."
            )
        if duplicados > 0:
            return (
                "Se detectaron intentos de reingreso con pases ya usados. "
                "Refuerce la validación visual del personal en puerta."
            )
        if porcentaje_aforo >= 0.7:
            return (
                "El aforo se acerca a su límite. Considere coordinar con el "
                "promotor de mejor desempeño para futuras fechas similares."
            )
        return (
            "Operación dentro de parámetros normales. Baja exposición a "
            "pérdidas y buen rendimiento operativo."
        )

    def generar_resumen(self, evento_id: int) -> ResumenEvento:
        evento = self._eventos.obtener_por_id(evento_id)
        if evento is None:
            raise NotFoundError(f"Evento {evento_id} no encontrado")

        validos = self._accesos.contar_por_evento_y_resultado(
            evento_id, ResultadoAcceso.VALIDO
        )
        duplicados = self._accesos.contar_por_evento_y_resultado(
            evento_id, ResultadoAcceso.DUPLICADO
        )
        rechazados = self._accesos.contar_por_evento_y_resultado(
            evento_id, ResultadoAcceso.RECHAZADO
        )

        comisiones = self._comisiones.listar(evento_id=evento_id)
        pendientes = sum(
            float(c.monto) for c in comisiones if c.estado == EstadoComision.PENDIENTE
        )
        liquidadas = sum(
            float(c.monto) for c in comisiones if c.estado == EstadoComision.LIQUIDADA
        )

        alertas_activas = self._alertas.listar(evento_id=evento_id, estado=EstadoAlerta.ACTIVA)
        porcentaje_aforo = validos / evento.aforo_maximo if evento.aforo_maximo else 0.0
        nivel_general = self._nivel_general(alertas_activas)

        return ResumenEvento(
            evento_id=evento.id,
            evento_nombre=evento.nombre,
            aforo_maximo=evento.aforo_maximo,
            accesos_validos=validos,
            accesos_duplicados=duplicados,
            accesos_rechazados=rechazados,
            porcentaje_aforo=porcentaje_aforo,
            comisiones_pendientes=pendientes,
            comisiones_liquidadas=liquidadas,
            alertas_activas=alertas_activas,
            nivel_riesgo_general=nivel_general.value,
            recomendacion=self._recomendacion(nivel_general, porcentaje_aforo, duplicados),
        )
