from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import RolUsuario


@dataclass
class Usuario:
    id: int | None
    nombre: str
    email: str
    password_hash: str
    rol: RolUsuario
    telefono: str | None = None
    estado: bool = True
    fecha_registro: datetime | None = None

    @property
    def esta_activo(self) -> bool:
        return self.estado
