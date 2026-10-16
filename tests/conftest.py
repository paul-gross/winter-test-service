"""Shared fixtures. No test here needs a live Postgres or RabbitMQ."""

from __future__ import annotations

import pytest
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from wts_persistence.internal.item_repository import WriteItemRepository


@compiles(BigInteger, "sqlite")
def _sqlite_bigint_as_integer(type_, compiler, **kw):
    # SQLite only auto-assigns primary keys for a column typed exactly INTEGER;
    # without this the BIGINT id in ItemEntity would never be generated.
    return "INTEGER"


@pytest.fixture
def sqlite_engine() -> Engine:
    """An in-memory SQLite engine standing in for Postgres at the engine seam.

    It stands in only for query behavior (ordering, limits, error wrapping). It
    does NOT stand in for the Postgres column types or timezone handling: SQLite
    returns naive datetimes with 1-second `CURRENT_TIMESTAMP` resolution, and the
    BigInteger id is compiled as INTEGER. The real Postgres DDL is pinned
    separately by compiling the entity against the Postgres dialect.

    `StaticPool` shares one connection so the in-memory database survives across
    sessions and across the threads the API test client serves requests on.
    """
    return create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


@pytest.fixture
def repo(sqlite_engine: Engine) -> WriteItemRepository:
    """The real write repository on `sqlite_engine`, schema already created."""
    repo = WriteItemRepository(sqlite_engine)
    repo.init_schema()
    return repo
