from dataclasses import dataclass, field

from app.application.risk_engine import RiskEngine
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.acceso_qr import AccesoQR
from app.domain.entities.alerta_riesgo import AlertaRiesgo
from app.domain.enums import EstadoInvitado, ResultadoAcceso, TipoAcceso, TipoAlerta
from app.domain.repositories.acceso_qr_repository import AccesoQRRepository
from app.domain.repositories.alerta_riesgo_repository import AlertaRiesgoRepository
from app.domain.repositories.evento_repository import EventoRepository
from app.domain.repositories.invitado_repository import InvitadoRepository


@dataclass
class ResultadoRegistroAcceso:
    acceso: AccesoQR
    aforo_actual: int
    aforo_maximo: int
    porcentaje_aforo: float
    alertas_generadas: list[AlertaRiesgo] = field(default_factory=list)


class AccesoService:
    def __init__(
        self,
        acceso_repository: AccesoQRRepository,
        invitado_repository: InvitadoRepository,
        evento_repository: EventoRepository,
        alerta_repository: AlertaRiesgoRepository,
        risk_engine: RiskEngine,
    ) -> None:
        self._accesos = acceso_repository
        self._invitados = invitado_repository
        self._eventos = evento_repository
        self._alertas = alerta_repository
        self._risk_engine = risk_engine

    def _aforo_actual(self, evento_id: int) -> int:
        return self._accesos.contar_por_evento_y_resultado(
            evento_id, ResultadoAcceso.VALIDO
        )

    def _alerta_cortesia_duplicada(self, evento_id: int) -> AlertaRiesgo:
        nivel, descripcion = self._risk_engine.evaluar_cortesia_duplicada()
        return self._alertas.crear(
            AlertaRiesgo(
                id=None,
                evento_id=evento_id,
                tipo_alerta=TipoAlerta.CORTESIA_DUPLICADA,
                nivel=nivel,
                descripcion=descripcion,
            )
        )

    def _evaluar_y_registrar_aforo(
        self, evento_id: int, aforo_maximo: int, fecha_evento
    ) -> tuple[int, list[AlertaRiesgo]]:
        aforo_actual = self._aforo_actual(evento_id)
        alertas: list[AlertaRiesgo] = []
        evaluacion = self._risk_engine.evaluar_aforo(
            accesos_validos=aforo_actual, aforo_maximo=aforo_maximo, fecha_evento=fecha_evento
        )
        if evaluacion.nivel is not None and evaluacion.descripcion is not None:
            alertas.append(
                self._alertas.crear(
                    AlertaRiesgo(
                        id=None,
                        evento_id=evento_id,
                        tipo_alerta=TipoAlerta.SOBREAFORO,
                        nivel=evaluacion.nivel,
                        descripcion=evaluacion.descripcion,
                    )
                )
            )
        return aforo_actual, alertas

    def registrar_acceso_qr(
        self, *, evento_id: int, qr_code: str
    ) -> ResultadoRegistroAcceso:
        evento = self._eventos.obtener_por_id(evento_id)
        if evento is None:
            raise NotFoundError(f"Evento {evento_id} no encontrado")

        # Con varias puertas activas, validar un QR y contar el aforo debe ser indivisible:
        # se serializa por evento y, además, el cambio pendiente -> usado es atómico.
        with self._accesos.bloquear_evento(evento_id):
            return self._registrar_acceso_qr_bloqueado(evento, qr_code)

    def _registrar_acceso_qr_bloqueado(self, evento, qr_code: str) -> ResultadoRegistroAcceso:
        evento_id = evento.id
        invitado = self._invitados.obtener_por_qr(qr_code)
        alertas: list[AlertaRiesgo] = []

        if invitado is None or invitado.evento_id != evento_id:
            resultado = ResultadoAcceso.RECHAZADO
            invitado_id = None
        elif invitado.estado == EstadoInvitado.USADO:
            resultado = ResultadoAcceso.DUPLICADO
            invitado_id = invitado.id
            alertas.append(self._alerta_cortesia_duplicada(evento_id))
        elif self._aforo_actual(evento_id) >= evento.aforo_maximo:
            resultado = ResultadoAcceso.RECHAZADO
            invitado_id = invitado.id
        elif self._invitados.marcar_usado_si_pendiente(invitado.id):
            resultado = ResultadoAcceso.VALIDO
            invitado_id = invitado.id
        else:
            # Otro lector usó este mismo pase en el mismo instante: este intento es un reuso.
            resultado = ResultadoAcceso.DUPLICADO
            invitado_id = invitado.id
            alertas.append(self._alerta_cortesia_duplicada(evento_id))

        acceso = self._accesos.crear(
            AccesoQR(
                id=None,
                evento_id=evento_id,
                invitado_id=invitado_id,
                tipo=TipoAcceso.QR,
                resultado=resultado,
            )
        )

        aforo_actual, alertas_aforo = self._evaluar_y_registrar_aforo(
            evento_id, evento.aforo_maximo, evento.fecha
        )
        alertas.extend(alertas_aforo)

        return ResultadoRegistroAcceso(
            acceso=acceso,
            aforo_actual=aforo_actual,
            aforo_maximo=evento.aforo_maximo,
            porcentaje_aforo=(aforo_actual / evento.aforo_maximo if evento.aforo_maximo else 0.0),
            alertas_generadas=alertas,
        )

    def registrar_cortesia_manual(
        self, *, evento_id: int, justificacion: str
    ) -> ResultadoRegistroAcceso:
        evento = self._eventos.obtener_por_id(evento_id)
        if evento is None:
            raise NotFoundError(f"Evento {evento_id} no encontrado")
        if not justificacion or not justificacion.strip():
            raise ValidationError(
                "La justificación es obligatoria para registrar una cortesía manual"
            )

        with self._accesos.bloquear_evento(evento_id):
            aforo_actual_previo = self._aforo_actual(evento_id)
            resultado = (
                ResultadoAcceso.RECHAZADO
                if aforo_actual_previo >= evento.aforo_maximo
                else ResultadoAcceso.VALIDO
            )

            acceso = self._accesos.crear(
                AccesoQR(
                    id=None,
                    evento_id=evento_id,
                    invitado_id=None,
                    tipo=TipoAcceso.CORTESIA_MANUAL,
                    resultado=resultado,
                    justificacion=justificacion,
                )
            )

            aforo_actual, alertas = self._evaluar_y_registrar_aforo(
                evento_id, evento.aforo_maximo, evento.fecha
            )

        return ResultadoRegistroAcceso(
            acceso=acceso,
            aforo_actual=aforo_actual,
            aforo_maximo=evento.aforo_maximo,
            porcentaje_aforo=(aforo_actual / evento.aforo_maximo if evento.aforo_maximo else 0.0),
            alertas_generadas=alertas,
        )

    def obtener(self, acceso_id: int) -> AccesoQR:
        acceso = self._accesos.obtener_por_id(acceso_id)
        if acceso is None:
            raise NotFoundError(f"Acceso {acceso_id} no encontrado")
        return acceso

    def listar(
        self, *, page: int = 1, limit: int = 20, evento_id: int | None = None
    ) -> tuple[list[AccesoQR], int]:
        return self._accesos.listar(page=page, limit=limit, evento_id=evento_id)

    def anular(self, acceso_id: int) -> AccesoQR:
        acceso = self.obtener(acceso_id)
        acceso.resultado = ResultadoAcceso.RECHAZADO
        return self._accesos.actualizar(acceso)

    def eliminar(self, acceso_id: int) -> None:
        self.obtener(acceso_id)
        self._accesos.eliminar(acceso_id)
