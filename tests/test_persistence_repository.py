from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from wts_persistence.domain.errors import RepositoryError
from wts_persistence.domain.item import ItemSource
from wts_persistence.internal.engine import create_db_engine
from wts_persistence.internal.entities import ItemEntity
from wts_persistence.internal.item_repository import (
    ReadItemRepository,
    WriteItemRepository,
)


def test_add_item_returns_domain_item_with_db_assigned_fields(repo):
    item = repo.add_item("hello", ItemSource.API)

    assert item.id == 1
    assert item.label == "hello"
    assert item.source is ItemSource.API
    assert item.created_at is not None


def test_list_items_orders_by_created_at_desc_then_id_desc_and_respects_limit(
    sqlite_engine, repo
):
    # Explicit timestamps (naive: SQLite does not keep tzinfo) in an order that
    # disagrees with id, so created_at is pinned as the primary key and id as
    # the tiebreaker. SQLite's own CURRENT_TIMESTAMP is too coarse to do that.
    rows = [
        (1, "march-a", datetime(2026, 3, 1)),
        (2, "january", datetime(2026, 1, 1)),
        (3, "february", datetime(2026, 2, 1)),
        (4, "march-b", datetime(2026, 3, 1)),
    ]
    with Session(sqlite_engine) as session:
        session.add_all(
            ItemEntity(id=id_, label=label, source="api", created_at=created_at)
            for id_, label, created_at in rows
        )
        session.commit()

    assert [i.label for i in repo.list_items()] == [
        "march-b",
        "march-a",
        "february",
        "january",
    ]
    assert [i.label for i in repo.list_items(limit=2)] == ["march-b", "march-a"]


def test_ping_is_true_against_a_reachable_engine(repo):
    assert repo.ping() is True


def test_ping_is_false_when_the_database_is_unreachable(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path}/missing-dir/db.sqlite")

    assert ReadItemRepository(engine).ping() is False


def test_list_items_wraps_driver_errors_in_repository_error(sqlite_engine):
    # Schema was never created, so the SELECT fails inside SQLAlchemy.
    with pytest.raises(RepositoryError, match="failed to list items"):
        ReadItemRepository(sqlite_engine).list_items()


def test_add_item_wraps_driver_errors_in_repository_error(sqlite_engine):
    with pytest.raises(RepositoryError, match="failed to add item"):
        WriteItemRepository(sqlite_engine).add_item("x", ItemSource.API)
