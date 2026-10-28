"""Pin the Postgres schema the entity declares, without needing a database.

The SQLite fixture used elsewhere cannot vouch for Postgres types, so compile the
entity against the Postgres dialect and check the DDL against the README schema.
"""

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from wts_persistence.internal.entities import ItemEntity


def _postgres_ddl() -> str:
    return str(CreateTable(ItemEntity.__table__).compile(dialect=postgresql.dialect()))


def _column_line(ddl: str, name: str) -> str:
    return next(
        ln.strip() for ln in ddl.splitlines() if ln.strip().startswith(name + " ")
    )


def test_id_is_a_bigserial_primary_key():
    ddl = _postgres_ddl()

    assert _column_line(ddl, "id").startswith("id BIGSERIAL NOT NULL")
    assert "PRIMARY KEY (id)" in ddl


def test_created_at_is_a_not_null_timestamptz_defaulting_to_now():
    line = _column_line(_postgres_ddl(), "created_at")

    assert "TIMESTAMP WITH TIME ZONE" in line
    assert "DEFAULT now()" in line
    assert "NOT NULL" in line


def test_label_and_source_are_not_null():
    ddl = _postgres_ddl()

    assert "NOT NULL" in _column_line(ddl, "label")
    assert "NOT NULL" in _column_line(ddl, "source")
