from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.domain.entities.invitado import Invitado
from app.domain.enums import EstadoInvitado
from app.domain.repositories.invitado_repository import InvitadoRepository
from app.infrastructure.models.invitado_model import InvitadoModel


def _to_entity(model: InvitadoModel) -> Invitado:
    return Invitado(
        id=model.id,
        evento_id=model.evento_id,
        promotor_id=model.promotor_id,
        nombre=model.nombre,
        qr_code=model.qr_code,
        estado=EstadoInvitado(model.estado),
        fecha_registro=model.fecha_registro,
    )


class SqlAlchemyInvitadoRepository(InvitadoRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def crear(self, invitado: Invitado) -> Invitado:
        model = InvitadoModel(
            evento_id=invitado.evento_id,
            promotor_id=invitado.promotor_id,
            nombre=invitado.nombre,
            qr_code=invitado.qr_code,
            estado=invitado.estado.value,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)

    def obtener_por_id(self, invitado_id: int) -> Invitado | None:
        model = self._session.get(InvitadoModel, invitado_id)
        return _to_entity(model) if model else None

    def obtener_por_qr(self, qr_code: str) -> Invitado | None:
        stmt = select(InvitadoModel).where(InvitadoModel.qr_code == qr_code)
        model = self._session.execute(stmt).scalar_one_or_none()
        return _to_entity(model) if model else None

    def listar(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        evento_id: int | None = None,
        promotor_id: int | None = None,
    ) -> tuple[list[Invitado], int]:
        stmt = select(InvitadoModel)
        count_stmt = select(func.count()).select_from(InvitadoModel)
        if evento_id is not None:
            stmt = stmt.where(InvitadoModel.evento_id == evento_id)
            count_stmt = count_stmt.where(InvitadoModel.evento_id == evento_id)
        if promotor_id is not None:
            stmt = stmt.where(InvitadoModel.promotor_id == promotor_id)
            count_stmt = count_stmt.where(InvitadoModel.promotor_id == promotor_id)
        total = self._session.execute(count_stmt).scalar_one()
        stmt = stmt.order_by(InvitadoModel.id).offset((page - 1) * limit).limit(limit)
        models = self._session.execute(stmt).scalars().all()
        return [_to_entity(m) for m in models], total

    def actualizar(self, invitado: Invitado) -> Invitado:
        model = self._session.get(InvitadoModel, invitado.id)
        if model is None:
            raise ValueError(f"Invitado {invitado.id} no encontrado")
        model.nombre = invitado.nombre
        model.estado = invitado.estado.value
        self._session.commit()
        self._session.refresh(model)
        return _to_entity(model)

    def marcar_usado_si_pendiente(self, invitado_id: int) -> bool:
        resultado = self._session.execute(
            update(InvitadoModel)
            .where(
                InvitadoModel.id == invitado_id,
                InvitadoModel.estado == EstadoInvitado.PENDIENTE.value,
            )
            .values(estado=EstadoInvitado.USADO.value)
        )
        self._session.commit()
        return resultado.rowcount == 1

    def eliminar(self, invitado_id: int) -> None:
        model = self._session.get(InvitadoModel, invitado_id)
        if model is not None:
            self._session.delete(model)
            self._session.commit()

    def contar_por_evento_y_promotor(self, evento_id: int, promotor_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(InvitadoModel)
            .where(
                InvitadoModel.evento_id == evento_id,
                InvitadoModel.promotor_id == promotor_id,
                InvitadoModel.estado == EstadoInvitado.USADO.value,
            )
        )
        return self._session.execute(stmt).scalar_one()
