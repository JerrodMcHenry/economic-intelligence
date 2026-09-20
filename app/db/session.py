"""Database engine and session management.

The engine (and the connection pool it owns) is created lazily and cached,
so importing this module — or starting the app without `DATABASE_URL` set —
never fails. A connection is only attempted the first time a database
operation is actually performed.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


class DatabaseNotConfiguredError(Exception):
    """Raised when a database operation is attempted without DATABASE_URL set."""


@lru_cache(maxsize=1)
def _get_engine() -> Engine:
    if not settings.database_url:
        raise DatabaseNotConfiguredError("DATABASE_URL is not configured.")
    # pool_pre_ping guards against stale connections (e.g. after a DB
    # restart) without any manual pool tuning.
    #
    # Increment #34 adds two bounds, both about failing fast rather than
    # tuning throughput (no measurements exist to justify tuning, so
    # pool_size/max_overflow are deliberately left at SQLAlchemy's
    # defaults):
    #
    # - `connect_timeout`: without it, psycopg waits on the OS default
    #   for a TCP connect, so a network partition to the database parks
    #   a worker thread for minutes instead of failing into the 503 that
    #   every route already handles correctly.
    # - `pool_recycle`: managed Postgres and the proxies in front of it
    #   drop idle connections silently. `pool_pre_ping` already repairs
    #   that, and recycling avoids paying the discovery round-trip.
    #
    # `application_name` makes this service identifiable in
    # `pg_stat_activity` when an operator is looking at who holds a
    # connection.
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=settings.database_pool_recycle_seconds,
        connect_args={
            "connect_timeout": settings.database_connect_timeout_seconds,
            "application_name": "macrochipz-api",
        },
    )


@lru_cache(maxsize=1)
def _get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=_get_engine(), autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """One transaction per use: commits on success, rolls back on any error.

    The caller performs whatever series of operations make up one logical
    unit of work inside this block; nothing inside that unit should call
    `session.commit()` or `session.rollback()` itself.
    """
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
