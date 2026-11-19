from app.core.exceptions import NotFoundError
from app.domain.entities.alerta_riesgo import AlertaRiesgo
from app.domain.enums import EstadoAlerta, NivelAlerta
from app.domain.repositories.alerta_riesgo_repository import AlertaRiesgoRepository


class AlertaService:
    def __init__(self, alerta_repository: AlertaRiesgoRepository) -> None:
        self._alertas = alerta_repository

    def obtener(self, alerta_id: int) -> AlertaRiesgo:
        alerta = self._alertas.obtener_por_id(alerta_id)
        if alerta is None:
            raise NotFoundError(f"Alerta {alerta_id} no encontrada")
        return alerta

    def listar(
        self,
        *,
        evento_id: int | None = None,
        nivel: NivelAlerta | None = None,
        estado: EstadoAlerta | None = None,
    ) -> list[AlertaRiesgo]:
        return self._alertas.listar(evento_id=evento_id, nivel=nivel, estado=estado)

    def actualizar_estado(self, alerta_id: int, estado: EstadoAlerta) -> AlertaRiesgo:
        alerta = self.obtener(alerta_id)
        alerta.estado = estado
        return self._alertas.actualizar(alerta)
