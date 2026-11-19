from enum import Enum


class RolUsuario(str, Enum):
    ADMINISTRADOR = "Administrador"
    PROMOTOR = "Promotor"
    PUERTA = "Puerta"


class EstadoEvento(str, Enum):
    PLANEADO = "planeado"
    EN_CURSO = "en curso"
    CERRADO = "cerrado"


class EstadoInvitado(str, Enum):
    PENDIENTE = "pendiente"
    USADO = "usado"


class EstadoComision(str, Enum):
    PENDIENTE = "pendiente"
    LIQUIDADA = "liquidada"


class TipoAcceso(str, Enum):
    QR = "qr"
    CORTESIA_MANUAL = "cortesia_manual"


class ResultadoAcceso(str, Enum):
    VALIDO = "valido"
    DUPLICADO = "duplicado"
    RECHAZADO = "rechazado"


class TipoAlerta(str, Enum):
    SOBREAFORO = "sobreaforo"
    COMISION_ATIPICA = "comision_atipica"
    CORTESIA_DUPLICADA = "cortesia_duplicada"


class NivelAlerta(str, Enum):
    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"


class EstadoAlerta(str, Enum):
    ACTIVA = "activa"
    RESUELTA = "resuelta"
