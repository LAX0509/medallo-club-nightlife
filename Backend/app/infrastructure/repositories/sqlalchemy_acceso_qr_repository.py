from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.domain.entities.acceso_qr import AccesoQR
from app.domain.enums import ResultadoAcceso, TipoAcceso
from app.domain.repositories.acceso_qr_repository import AccesoQRRepository
from app.infrastructure.models.acceso_qr_model import AccesoQRModel


def _to_entity(model: AccesoQRModel) -> AccesoQR:
    return AccesoQR(
        id=model.id,
        evento_id=model.evento_id,
        invitado_id=model.invitado_id,
        tipo=TipoAcceso(model.tipo),
        resultado=ResultadoAcceso(model.resultado),
        justificacion=model.justificacion,
        fecha_hora=model.fecha_hora,
    )


# Espacio de claves de los bloqueos asesores de PostgreSQL (uno por evento).
_BASE_CLAVE_BLOQUEO = 7_700_000_000


class SqlAlchemyAccesoQRRepository(AccesoQRRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def bloquear_evento(self, evento_id: int) -> Iterator[None]:
        """Exclusión mutua por evento para que dos puertas no validen a la vez el mismo QR
        ni superen el aforo. Usa una conexión dedicada: el bloqueo sobrevive a los ``commit``
        que hace la sesión durante el registro. En motores sin bloqueos asesores (SQLite, de
        un solo escritor) no hace nada.
        """
        motor = self._session.get_bind()
        if motor.dialect.name != "postgresql":
            yield
            return
        clave = _BASE_CLAVE_BLOQUEO + evento_id
        with motor.connect() as conexion:
            conexion.execute(text("SELECT pg_advisory_lock(:clave)"), {"clave": clave})
            try:
                yield
            finally:
                conexion.execute(text("SELECT pg_advisory_unlock(:clave)"), {"clave": clave})

    def crear(self, acceso: AccesoQR) -> AccesoQR:
        model = AccesoQRModel(
            evento_id=acceso.evento_id,
            invitado_id=acceso.invitado_id,
            tipo=acceso.tipo.value,
            resultado=acceso.resultado.value,
            justificacion=acceso.justificacion,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)

    def obtener_por_id(self, acceso_id: int) -> AccesoQR | None:
        model = self._session.get(AccesoQRModel, acceso_id)
        return _to_entity(model) if model else None

    def listar(
        self, *, page: int = 1, limit: int = 20, evento_id: int | None = None
    ) -> tuple[list[AccesoQR], int]:
        stmt = select(AccesoQRModel)
        count_stmt = select(func.count()).select_from(AccesoQRModel)
        if evento_id is not None:
            stmt = stmt.where(AccesoQRModel.evento_id == evento_id)
            count_stmt = count_stmt.where(AccesoQRModel.evento_id == evento_id)
        total = self._session.execute(count_stmt).scalar_one()
        stmt = (
            stmt.order_by(AccesoQRModel.fecha_hora.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        models = self._session.execute(stmt).scalars().all()
        return [_to_entity(m) for m in models], total

    def actualizar(self, acceso: AccesoQR) -> AccesoQR:
        model = self._session.get(AccesoQRModel, acceso.id)
        if model is None:
            raise ValueError(f"Acceso {acceso.id} no encontrado")
        model.resultado = acceso.resultado.value
        model.justificacion = acceso.justificacion
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)

    def eliminar(self, acceso_id: int) -> None:
        model = self._session.get(AccesoQRModel, acceso_id)
        if model is not None:
            self._session.delete(model)
            self._session.commit()

    def contar_por_evento_y_resultado(
        self, evento_id: int, resultado: ResultadoAcceso
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(AccesoQRModel)
            .where(
                AccesoQRModel.evento_id == evento_id,
                AccesoQRModel.resultado == resultado.value,
            )
        )
        return self._session.execute(stmt).scalar_one()
