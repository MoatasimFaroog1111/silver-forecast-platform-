from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith('postgres://'):
        return 'postgresql+psycopg://' + database_url[len('postgres://'):]
    if database_url.startswith('postgresql://') and '+psycopg' not in database_url:
        return 'postgresql+psycopg://' + database_url[len('postgresql://'):]
    return database_url


def build_database_engine(database_url: str) -> Engine:
    normalized = normalize_database_url(database_url)
    if normalized.startswith('sqlite:///'):
        path = Path(normalized.removeprefix('sqlite:///'))
        path.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(normalized, future=True, connect_args={'check_same_thread': False})
    return create_engine(normalized, future=True, pool_pre_ping=True)


def build_session_factory(engine: Engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
