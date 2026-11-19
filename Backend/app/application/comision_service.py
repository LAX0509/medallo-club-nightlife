from decimal import Decimal

from app.application.risk_engine import RiskEngine
from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.alerta_riesgo import AlertaRiesgo
from app.domain.entities.comision import Comision
from app.domain.enums import EstadoComision, NivelAlerta, RolUsuario, TipoAlerta
from app.domain.repositories.alerta_riesgo_repository import AlertaRiesgoRepository
from app.domain.repositories.comision_repository import ComisionRepository
from app.domain.repositories.evento_repository import EventoRepository
from app.domain.repositories.invitado_repository import InvitadoRepository
from app.domain.repositories.usuario_repository import UsuarioRepository


class ComisionService:
    def __init__(
        self,
        comision_repository: ComisionRepository,
        invitado_repository: InvitadoRepository,
        evento_repository: EventoRepository,
        usuario_repository: UsuarioRepository,
        alerta_repository: AlertaRiesgoRepository,
        risk_engine: RiskEngine,
        settings: Settings,
    ) -> None:
        self._comisiones = comision_repository
        self._invitados = invitado_repository
        self._eventos = evento_repository
        self._usuarios = usuario_repository
        self._alertas = alerta_repository
        self._risk_engine = risk_engine
        self._settings = settings

    def _calcular_monto_sugerido(
        self, *, evento_id: int, promotor_id: int, porcentaje: Decimal
    ) -> Decimal:
        invitados_validados = self._invitados.contar_por_evento_y_promotor(
            evento_id, promotor_id
        )
        base = Decimal(str(self._settings.valor_base_por_invitado_cop))
        monto = (base * invitados_validados * porcentaje / Decimal("100")).quantize(
            Decimal("0.01")
        )
        return monto

    def crear(
        self, *, promotor_id: int, evento_id: int, porcentaje: Decimal
    ) -> Comision:
        promotor = self._usuarios.obtener_por_id(promotor_id)
        if promotor is None:
            raise NotFoundError(f"Promotor {promotor_id} no encontrado")
        if promotor.rol != RolUsuario.PROMOTOR:
            raise ValidationError(f"El usuario {promotor_id} no tiene rol Promotor")
        if self._eventos.obtener_por_id(evento_id) is None:
            raise NotFoundError(f"Evento {evento_id} no encontrado")

        monto_sugerido = self._calcular_monto_sugerido(
            evento_id=evento_id, promotor_id=promotor_id, porcentaje=porcentaje
        )
        comision = Comision(
            id=None,
            promotor_id=promotor_id,
            evento_id=evento_id,
            porcentaje=porcentaje,
            monto=monto_sugerido,
        )
        return self._comisiones.crear(comision)

    def obtener(self, comision_id: int) -> Comision:
        comision = self._comisiones.obtener_por_id(comision_id)
        if comision is None:
            raise NotFoundError(f"Comisión {comision_id} no encontrada")
        return comision

    def listar(
        self,
        *,
        promotor_id: int | None = None,
        evento_id: int | None = None,
        estado: EstadoComision | None = None,
    ) -> list[Comision]:
        return self._comisiones.listar(
            promotor_id=promotor_id, evento_id=evento_id, estado=estado
        )

    def actualizar(
        self,
        comision_id: int,
        *,
        estado: EstadoComision | None,
        monto: Decimal | None,
    ) -> tuple[Comision, AlertaRiesgo | None]:
        comision = self.obtener(comision_id)
        alerta_generada: AlertaRiesgo | None = None

        if monto is not None:
            historico = self._comisiones.listar_montos_historicos(comision.promotor_id)
            evaluacion = self._risk_engine.evaluar_comision_atipica(
                monto_nuevo=float(monto), historico=historico
            )
            comision.monto = monto
            if evaluacion.es_atipica and evaluacion.nivel is not None:
                alerta_generada = self._alertas.crear(
                    AlertaRiesgo(
                        id=None,
                        evento_id=comision.evento_id,
                        tipo_alerta=TipoAlerta.COMISION_ATIPICA,
                        nivel=evaluacion.nivel,
                        descripcion=evaluacion.descripcion or "Comisión atípica detectada",
                    )
                )

        if estado is not None:
            comision.estado = estado

        comision_actualizada = self._comisiones.actualizar(comision)
        return comision_actualizada, alerta_generada
