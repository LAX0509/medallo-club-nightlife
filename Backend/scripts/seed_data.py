"""Script de arranque: crea el esquema (si no existe) y datos de demostración.

Resuelve el problema de "huevo y gallina" de RBAC: crear un usuario vía la
API requiere ya tener un token de Administrador, así que el primer
administrador se crea directamente contra la base de datos usando la
misma capa de aplicación (UsuarioService), sin pasar por HTTP.

Uso:
    python -m scripts.seed_data
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from datetime import date, timedelta  # noqa: E402

from app.application.evento_service import EventoService  # noqa: E402
from app.application.invitado_service import InvitadoService  # noqa: E402
from app.application.usuario_service import UsuarioService  # noqa: E402
from app.core.exceptions import ConflictError  # noqa: E402
from app.domain.enums import RolUsuario  # noqa: E402
from app.infrastructure.database.session import Base, SessionLocal, engine  # noqa: E402
from app.infrastructure.models.reserva_model import ReservaModel  # noqa: E402,F401
from app.infrastructure.repositories import (  # noqa: E402
    SqlAlchemyEventoRepository,
    SqlAlchemyInvitadoRepository,
    SqlAlchemyUsuarioRepository,
)


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        usuario_repository = SqlAlchemyUsuarioRepository(db)
        usuario_service = UsuarioService(usuario_repository)
        evento_service = EventoService(SqlAlchemyEventoRepository(db))
        invitado_service = InvitadoService(
            SqlAlchemyInvitadoRepository(db),
            SqlAlchemyEventoRepository(db),
            usuario_repository,
        )

        try:
            admin = usuario_service.registrar(
                nombre="Admin Principal",
                email="admin@medalloclub.com",
                password="Admin123",
                rol=RolUsuario.ADMINISTRADOR,
                telefono="3000000000",
            )
            print(f"Administrador creado: {admin.email} / Admin123")
        except ConflictError:
            admin = usuario_repository.obtener_por_email("admin@medalloclub.com")
            print("El administrador demo ya existía, se omite.")

        try:
            promotor = usuario_service.registrar(
                nombre="Carla Promotora",
                email="promotora@medalloclub.com",
                password="Promotor123",
                rol=RolUsuario.PROMOTOR,
                telefono="3001112233",
            )
            print(f"Promotor creado: {promotor.email} / Promotor123")
        except ConflictError:
            print("El promotor demo ya existía, se omite.")

        try:
            puerta = usuario_service.registrar(
                nombre="Puerta Principal",
                email="puerta@medalloclub.com",
                password="Puerta123",
                rol=RolUsuario.PUERTA,
                telefono="3002223344",
            )
            print(f"Usuario de puerta creado: {puerta.email} / Puerta123")
        except ConflictError:
            print("El usuario de puerta demo ya existía, se omite.")

        evento = evento_service.crear(
            administrador_id=admin.id,
            nombre="Noche Retro Viernes",
            fecha=date.today() + timedelta(days=2),
            aforo_maximo=150,
        )
        print(f"Evento demo creado: {evento.nombre} (id={evento.id})")

        promotor_registrado = usuario_repository.obtener_por_email(
            "promotora@medalloclub.com"
        )
        for nombre in ("María Gómez", "Juan Pérez", "Laura Restrepo"):
            invitado = invitado_service.registrar(
                nombre=nombre, evento_id=evento.id, promotor_id=promotor_registrado.id
            )
            print(f"  Invitado: {invitado.nombre} -> QR {invitado.qr_code}")

        print("\nSeed completado correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
