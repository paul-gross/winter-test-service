"""SQLAlchemy engine construction. The DATABASE_URL → engine translation lives here."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# Default points at the standalone Postgres container published on port 5545.
_DEFAULT_DATABASE_URL = "postgresql://wts:wts@localhost:5545/wts"


def database_url() -> str:
    """Resolve the database URL, normalized to the psycopg3 driver."""
    raw = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)
    # SQLAlchemy needs the explicit psycopg3 driver; accept the plain form too.
    return raw.replace("postgresql://", "postgresql+psycopg://", 1)


def create_db_engine(url: str | None = None) -> Engine:
    """Build a pooled engine. `pool_pre_ping` recovers dropped connections."""
    return create_engine(url or database_url(), pool_pre_ping=True)
