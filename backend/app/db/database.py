"""
NexClip database engine and session management.
"""

from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# SQLite needs a busy timeout because API requests, Celery workers, and caption rendering
# can overlap on the same file-backed database during local development.
connect_args = {"check_same_thread": False, "timeout": 30} if settings.is_sqlite else {}
pool_kwargs = (
    {"pool_size": settings.DB_POOL_SIZE, "max_overflow": settings.DB_MAX_OVERFLOW}
    if not settings.is_sqlite
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
    **pool_kwargs,
)


if settings.is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
