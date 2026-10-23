import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tecnotextil.db")
_IS_SQLITE = SQLALCHEMY_DATABASE_URL.startswith("sqlite")


def habilitar_foreign_keys(eng) -> None:
    """O SQLite NÃO aplica chaves estrangeiras por padrão; liga a cada conexão."""

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if _IS_SQLITE else {},
)
if _IS_SQLITE:
    habilitar_foreign_keys(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
