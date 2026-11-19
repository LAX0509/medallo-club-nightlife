class DomainError(Exception):
    """Error base de reglas de negocio del dominio Nightlife Data Scientist."""


class NotFoundError(DomainError):
    """El recurso solicitado no existe."""


class ConflictError(DomainError):
    """La operación entra en conflicto con el estado actual de los datos (duplicados, etc.)."""


class ValidationError(DomainError):
    """Los datos suministrados no cumplen una regla de negocio."""


class AuthenticationError(DomainError):
    """Credenciales inválidas o token inválido."""


class AuthorizationError(DomainError):
    """El usuario autenticado no tiene permisos para la acción solicitada."""
