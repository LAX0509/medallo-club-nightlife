from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.comision import Comision
from app.domain.enums import EstadoComision
from app.domain.repositories.comision_repository import ComisionRepository
from app.infrastructure.models.comision_model import ComisionModel


def _to_entity(model: ComisionModel) -> Comision:
    return Comision(
        id=model.id,
        promotor_id=model.promotor_id,
        evento_id=model.evento_id,
        porcentaje=Decimal(str(model.porcentaje)),
        monto=Decimal(str(model.monto)),
        estado=EstadoComision(model.estado),
        fecha_liquidacion=model.fecha_liquidacion,
    )


class SqlAlchemyComisionRepository(ComisionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def crear(self, comision: Comision) -> Comision:
        model = ComisionModel(
            promotor_id=comision.promotor_id,
            evento_id=comision.evento_id,
            porcentaje=comision.porcentaje,
            monto=comision.monto,
            estado=comision.estado.value,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)

    def obtener_por_id(self, comision_id: int) -> Comision | None:
        model = self._session.get(ComisionModel, comision_id)
        return _to_entity(model) if model else None

    def listar(
        self,
        *,
        promotor_id: int | None = None,
        evento_id: int | None = None,
        estado: EstadoComision | None = None,
    ) -> list[Comision]:
        stmt = select(ComisionModel)
        if promotor_id is not None:
            stmt = stmt.where(ComisionModel.promotor_id == promotor_id)
        if evento_id is not None:
            stmt = stmt.where(ComisionModel.evento_id == evento_id)
        if estado is not None:
            stmt = stmt.where(ComisionModel.estado == estado.value)
        stmt = stmt.order_by(ComisionModel.id.desc())
        models = self._session.execute(stmt).scalars().all()
        return [_to_entity(m) for m in models]

    def actualizar(self, comision: Comision) -> Comision:
        model = self._session.get(ComisionModel, comision.id)
        if model is None:
            raise ValueError(f"Comisión {comision.id} no encontrada")
        model.porcentaje = comision.porcentaje
        model.monto = comision.monto
        model.estado = comision.estado.value
        if comision.estado == EstadoComision.LIQUIDADA and model.fecha_liquidacion is None:
            model.fecha_liquidacion = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)

    def listar_montos_historicos(self, promotor_id: int) -> list[float]:
        stmt = select(ComisionModel.monto).where(
            ComisionModel.promotor_id == promotor_id,
            ComisionModel.estado == EstadoComision.LIQUIDADA.value,
        )
        return [float(m) for m in self._session.execute(stmt).scalars().all()]
