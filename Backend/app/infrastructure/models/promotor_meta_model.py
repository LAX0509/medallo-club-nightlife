from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class PromotorMetaModel(Base):
    __tablename__ = "promotores_metas_evento"
    __table_args__ = (
        UniqueConstraint("promotor_id", "evento_id", name="uq_promotor_meta_evento"),
        CheckConstraint("objetivo > 0", name="ck_promotor_meta_objetivo_positivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    promotor_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evento_id: Mapped[int] = mapped_column(
        ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    objetivo: Mapped[int] = mapped_column(Integer, nullable=False)
