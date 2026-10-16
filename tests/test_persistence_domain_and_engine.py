import pytest

from wts_persistence.domain.item import ItemSource
from wts_persistence.internal.engine import database_url

PG_DEFAULT = "postgresql+psycopg://wts:wts@localhost:5545/wts"


def test_item_source_round_trips_from_stored_string():
    assert ItemSource("api") is ItemSource.API
    assert ItemSource("worker") is ItemSource.WORKER
    with pytest.raises(ValueError):
        ItemSource("nope")


def test_database_url_defaults_to_local_postgres_with_psycopg3_driver(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url() == PG_DEFAULT


def test_database_url_rewrites_plain_scheme_only_once(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:1/db?x=postgresql://y")
    assert database_url() == "postgresql+psycopg://u:p@h:1/db?x=postgresql://y"


def test_database_url_leaves_explicit_driver_untouched(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/db")
    assert database_url() == "postgresql+psycopg://u:p@h/db"
