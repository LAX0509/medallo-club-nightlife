from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import EstadoInvitado


@dataclass
class Invitado:
    id: int | None
    evento_id: int
    promotor_id: int
    nombre: str
    qr_code: str
    estado: EstadoInvitado = EstadoInvitado.PENDIENTE
    fecha_registro: datetime | None = None

    @property
    def esta_disponible(self) -> bool:
        return self.estado == EstadoInvitado.PENDIENTE
