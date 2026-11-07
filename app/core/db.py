"""Database session for the APIs (one engine per process, one session per request).

Connection pool (US-47, T-47.2): each worker keeps DB_POOL_SIZE connections open (default 10) and can open
DB_POOL_OVERFLOW more under a peak (default 10), so a request does not pay for a new TLS connection to RDS.
pool_pre_ping drops a connection RDS closed; pool_recycle renews connections every 30 minutes.
"""

import os

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url,
        pool_size=int(os.getenv("DB_POOL_SIZE") or "10"),
        max_overflow=int(os.getenv("DB_POOL_OVERFLOW") or "10"),
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def get_session() -> Iterator[Session]:
    """FastAPI dependency. Tests replace it with a session that rolls back."""
    with Session(get_engine()) as session:
        yield session
