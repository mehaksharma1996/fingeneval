"""Database engine, transaction scope, and tenant-safe query helpers."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import enterprise_settings
from .models import Base, User


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or enterprise_settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def create_schema(target_engine: Engine | None = None) -> None:
    Base.metadata.create_all(target_engine or engine)


def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_user_in_tenant(session: Session, user_id: str, tenant_id: str | None = None) -> User | None:
    statement = select(User).where(User.id == user_id, User.active.is_(True))
    if tenant_id:
        statement = statement.where(User.tenant_id == tenant_id)
    return session.scalar(statement)


def tenant_get(session: Session, model, entity_id: str, tenant_id: str):
    """Fetch one row only when its tenant matches; prevents identifier probing."""
    return session.scalar(select(model).where(model.id == entity_id, model.tenant_id == tenant_id))
