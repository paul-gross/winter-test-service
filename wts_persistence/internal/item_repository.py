"""SQLAlchemy item repositories. All SQLAlchemy usage is confined to this file."""

from __future__ import annotations

import logging

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from wts_persistence.domain.errors import RepositoryError
from wts_persistence.domain.item import Item, ItemSource
from wts_persistence.internal.entities import Base, ItemEntity
from wts_persistence.repositories.item_repository import (
    IReadItemRepository,
    IWriteItemRepository,
)

logger = logging.getLogger(__name__)


class ReadItemRepository:
    """Read-only SQLAlchemy adapter for items. All read SQL is confined here."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ping(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False

    def list_items(self, limit: int = 100) -> list[Item]:
        try:
            with Session(self._engine) as session:
                stmt = (
                    select(ItemEntity)
                    .order_by(ItemEntity.created_at.desc(), ItemEntity.id.desc())
                    .limit(limit)
                )
                return [_to_domain(e) for e in session.scalars(stmt).all()]
        except SQLAlchemyError as exc:
            raise self._wrap(exc, "failed to list items")

    @staticmethod
    def _wrap(exc: SQLAlchemyError, message: str) -> RepositoryError:
        # Log once at the wrap site so callers never re-log the library error.
        logger.warning("%s: %s", message, exc)
        return RepositoryError(message)


class WriteItemRepository(ReadItemRepository):
    """Read-write SQLAlchemy adapter. Mutations live here; reads are inherited."""

    def init_schema(self) -> None:
        try:
            Base.metadata.create_all(self._engine)
        except SQLAlchemyError as exc:
            raise self._wrap(exc, "failed to initialise schema")

    def add_item(self, label: str, source: ItemSource) -> Item:
        try:
            with Session(self._engine) as session:
                entity = ItemEntity(label=label, source=source.value)
                session.add(entity)
                session.commit()
                session.refresh(entity)  # load DB-assigned id + created_at
                return _to_domain(entity)
        except SQLAlchemyError as exc:
            raise self._wrap(exc, "failed to add item")


def _to_domain(entity: ItemEntity) -> Item:
    """Map an ORM row to the domain object — entities never escape this package."""
    return Item(
        id=entity.id,
        label=entity.label,
        source=ItemSource(entity.source),
        created_at=entity.created_at,
    )


# Typecheck-time conformance sentinels: pin each adapter to its Protocol seam.
# Because IWriteItemRepository extends IReadItemRepository, the two sentinels
# together pin both read and write surfaces.
def _conforms_read_item_repository(x: ReadItemRepository) -> IReadItemRepository:
    return x


def _conforms_write_item_repository(x: WriteItemRepository) -> IWriteItemRepository:
    return x
