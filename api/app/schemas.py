"""Pydantic request/response models — the api's transport surface, kept out of the domain."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from wts_persistence.domain.item import ItemSource


class ItemCreate(BaseModel):
    """Request body for POST /api/items."""

    label: str = ""


class ItemRead(BaseModel):
    """Response shape for an item. Built from the `Item` domain object."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    source: ItemSource
    created_at: datetime


class HealthRead(BaseModel):
    """Response shape for GET /api/health."""

    status: str
    db: str
