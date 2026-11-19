from abc import ABC, abstractmethod

from app.domain.entities.alerta_riesgo import AlertaRiesgo
from app.domain.enums import EstadoAlerta, NivelAlerta


class AlertaRiesgoRepository(ABC):
    @abstractmethod
    def crear(self, alerta: AlertaRiesgo) -> AlertaRiesgo: ...

    @abstractmethod
    def obtener_por_id(self, alerta_id: int) -> AlertaRiesgo | None: ...

    @abstractmethod
    def listar(
        self,
        *,
        evento_id: int | None = None,
        nivel: NivelAlerta | None = None,
        estado: EstadoAlerta | None = None,
    ) -> list[AlertaRiesgo]: ...

    @abstractmethod
    def actualizar(self, alerta: AlertaRiesgo) -> AlertaRiesgo: ...
