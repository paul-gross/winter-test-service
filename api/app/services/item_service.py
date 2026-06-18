"""The item domain service. Owns the business rules for adding items; no SQL."""

from __future__ import annotations

from wts_persistence.domain.item import Item, ItemSource
from wts_persistence.repositories.item_repository import IWriteItemRepository


class ItemValidationError(ValueError):
    """Raised when an item fails a domain rule (e.g. an empty label)."""


class ItemService:
    """Orchestrates item mutations. Depends on the write-repository Protocol seam."""

    def __init__(self, items: IWriteItemRepository) -> None:
        self._items = items

    def add_item(self, label: str) -> Item:
        cleaned = label.strip()
        if not cleaned:
            raise ItemValidationError("label is required and must not be empty")
        return self._items.add_item(cleaned, ItemSource.API)
