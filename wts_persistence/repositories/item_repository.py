"""The read/write Protocol seams for item persistence.

Consumers depend on these Protocols, never on the SQLAlchemy adapter behind
them. The split follows the winter repository-pattern convention: `Read` is
usable anywhere (including directly from route handlers that only display data),
while `Write` carries mutations that a domain service orchestrates.
"""

from __future__ import annotations

from typing import Protocol

from wts_persistence.domain.item import Item, ItemSource


class IReadItemRepository(Protocol):
    """Read-only operations against the item store."""

    def ping(self) -> bool: ...

    def list_items(self, limit: int = 100) -> list[Item]: ...


class IWriteItemRepository(IReadItemRepository, Protocol):
    """Read-write variant. Services that mutate item state depend on this."""

    def init_schema(self) -> None: ...

    def add_item(self, label: str, source: ItemSource) -> Item: ...
