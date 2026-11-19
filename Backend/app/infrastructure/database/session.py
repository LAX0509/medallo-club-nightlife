from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.tareas import es_serverless

settings = get_settings()

if es_serverless():
    # Serverless: cada invocación es efímera; un pool por instancia agotaría las conexiones de la base gratuita.
    _opciones_pool = {"poolclass": NullPool}
elif settings.database_url.startswith("postgresql"):
    # El registro de accesos toma una conexión dedicada por puerta activa (bloqueo por evento).
    _opciones_pool = {"pool_size": 10, "max_overflow": 30}
else:
    _opciones_pool = {}
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True, **_opciones_pool)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM de infraestructura."""


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
