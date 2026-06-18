"""The `Item` domain object and its source — what the app uses, no storage detail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ItemSource(str, Enum):
    """Who created an item: a user via the api, or the background worker."""

    API = "api"
    WORKER = "worker"


@dataclass(frozen=True)
class Item:
    """A persisted item. The domain currency every layer above storage uses."""

    id: int
    label: str
    source: ItemSource
    created_at: datetime
