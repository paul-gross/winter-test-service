"""FastAPI dependency wiring — the composition root for the api's collaborators.

Routes declare what they need as `Annotated[..., Depends(...)]`; this module is
the one place the Protocol seams are bound to their SQLAlchemy adapters.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.engine import Engine

from app.services.item_service import ItemService
from wts_persistence.internal.engine import create_db_engine
from wts_persistence.internal.item_repository import WriteItemRepository
from wts_persistence.repositories.item_repository import (
    IReadItemRepository,
    IWriteItemRepository,
)


@lru_cache
def get_engine() -> Engine:
    """The process-wide SQLAlchemy engine (one pool, built lazily)."""
    return create_db_engine()


def build_write_item_repository() -> WriteItemRepository:
    """Construct the write repository outside the Depends graph (lifespan startup)."""
    return WriteItemRepository(get_engine())


def get_write_item_repository(
    engine: Annotated[Engine, Depends(get_engine)],
) -> IWriteItemRepository:
    return WriteItemRepository(engine)


def get_read_item_repository(
    repo: Annotated[IWriteItemRepository, Depends(get_write_item_repository)],
) -> IReadItemRepository:
    # The write repo satisfies the read supertype; declaring the read Protocol
    # keeps read-only intent visible where reads are all a route needs.
    return repo


def get_item_service(
    repo: Annotated[IWriteItemRepository, Depends(get_write_item_repository)],
) -> ItemService:
    return ItemService(repo)


ReadItemRepositoryDep = Annotated[IReadItemRepository, Depends(get_read_item_repository)]
ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
