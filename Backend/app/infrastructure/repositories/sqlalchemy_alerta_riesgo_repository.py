from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.alerta_riesgo import AlertaRiesgo
from app.domain.enums import EstadoAlerta, NivelAlerta, TipoAlerta
from app.domain.repositories.alerta_riesgo_repository import AlertaRiesgoRepository
from app.infrastructure.models.alerta_riesgo_model import AlertaRiesgoModel


def _to_entity(model: AlertaRiesgoModel) -> AlertaRiesgo:
    return AlertaRiesgo(
        id=model.id,
        evento_id=model.evento_id,
        tipo_alerta=TipoAlerta(model.tipo_alerta),
        nivel=NivelAlerta(model.nivel),
        descripcion=model.descripcion,
        estado=EstadoAlerta(model.estado),
        fecha_hora=model.fecha_hora,
    )


class SqlAlchemyAlertaRiesgoRepository(AlertaRiesgoRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def crear(self, alerta: AlertaRiesgo) -> AlertaRiesgo:
        model = AlertaRiesgoModel(
            evento_id=alerta.evento_id,
            tipo_alerta=alerta.tipo_alerta.value,
            nivel=alerta.nivel.value,
            descripcion=alerta.descripcion,
            estado=alerta.estado.value,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)

    def obtener_por_id(self, alerta_id: int) -> AlertaRiesgo | None:
        model = self._session.get(AlertaRiesgoModel, alerta_id)
        return _to_entity(model) if model else None

    def listar(
        self,
        *,
        evento_id: int | None = None,
        nivel: NivelAlerta | None = None,
        estado: EstadoAlerta | None = None,
    ) -> list[AlertaRiesgo]:
        stmt = select(AlertaRiesgoModel)
        if evento_id is not None:
            stmt = stmt.where(AlertaRiesgoModel.evento_id == evento_id)
        if nivel is not None:
            stmt = stmt.where(AlertaRiesgoModel.nivel == nivel.value)
        if estado is not None:
            stmt = stmt.where(AlertaRiesgoModel.estado == estado.value)
        stmt = stmt.order_by(AlertaRiesgoModel.fecha_hora.desc())
        models = self._session.execute(stmt).scalars().all()
        return [_to_entity(m) for m in models]

    def actualizar(self, alerta: AlertaRiesgo) -> AlertaRiesgo:
        model = self._session.get(AlertaRiesgoModel, alerta.id)
        if model is None:
            raise ValueError(f"Alerta {alerta.id} no encontrada")
        model.estado = alerta.estado.value
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)
