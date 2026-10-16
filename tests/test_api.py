import pytest
from fastapi.testclient import TestClient

from app import deps
from app import main as api_main
from app.services.item_service import ItemService, ItemValidationError
from wts_persistence.domain.errors import RepositoryError
from wts_persistence.domain.item import ItemSource
from wts_persistence.internal.engine import create_db_engine


@pytest.fixture
def client(repo, sqlite_engine):
    # Override at the engine seam so requests run the real get_*_repository
    # wiring and the real WriteItemRepository. `repo` creates the schema.
    # No `with` block: that would run the lifespan (DB schema init with backoff).
    api_main.app.dependency_overrides[deps.get_engine] = lambda: sqlite_engine
    yield TestClient(api_main.app)
    api_main.app.dependency_overrides.clear()


def test_item_service_strips_label_and_tags_source_api(repo):
    item = ItemService(repo).add_item("  hello  ")

    assert item.label == "hello"
    assert item.source is ItemSource.API


@pytest.mark.parametrize("label", ["", "   ", "\t\n"])
def test_item_service_rejects_blank_labels(repo, label):
    with pytest.raises(ItemValidationError):
        ItemService(repo).add_item(label)
    assert repo.list_items() == []


def test_health_reports_db_ok(client):
    assert client.get("/api/health").json() == {"status": "ok", "db": "ok"}


def test_health_reports_db_down_when_the_engine_is_unreachable(client, tmp_path):
    dead = create_db_engine(f"sqlite:///{tmp_path}/missing-dir/db.sqlite")
    api_main.app.dependency_overrides[deps.get_engine] = lambda: dead

    assert client.get("/api/health").json() == {"status": "ok", "db": "down"}


def test_create_item_returns_201_and_lists_newest_first(client):
    created = client.post("/api/items", json={"label": " first "})
    client.post("/api/items", json={"label": "second"})

    assert created.status_code == 201
    assert created.json()["label"] == "first"
    assert created.json()["source"] == "api"

    listed = client.get("/api/items")
    assert [i["label"] for i in listed.json()] == ["second", "first"]


def test_created_item_is_persisted_through_the_real_repository(client, repo):
    client.post("/api/items", json={"label": "kept"})

    assert [i.label for i in repo.list_items()] == ["kept"]


def test_create_item_with_blank_label_is_400(client):
    resp = client.post("/api/items", json={"label": "  "})

    assert resp.status_code == 400
    assert "label" in resp.json()["detail"]


def test_chaos_error_log_writes_n_raw_lines_to_stderr(client, capsys):
    resp = client.post("/api/chaos/error-log?n=3")

    assert resp.json() == {"emitted": 3}
    err = capsys.readouterr().err
    assert [ln for ln in err.splitlines() if ln.startswith("CHAOS ERROR")] == [
        "CHAOS ERROR 1/3",
        "CHAOS ERROR 2/3",
        "CHAOS ERROR 3/3",
    ]


def test_chaos_error_log_rejects_non_positive_n(client):
    assert client.post("/api/chaos/error-log?n=0").status_code == 422


def test_boot_delay_sleeps_only_when_configured(monkeypatch):
    sleeps = []
    monkeypatch.setattr(api_main.time, "sleep", sleeps.append)

    monkeypatch.delenv("WTS_BOOT_DELAY_SECONDS", raising=False)
    api_main._boot_delay()
    assert sleeps == []

    monkeypatch.setenv("WTS_BOOT_DELAY_SECONDS", "1.5")
    api_main._boot_delay()
    assert sleeps == [1.5]


def test_schema_init_retries_until_the_database_is_ready(monkeypatch):
    class FlakySchemaRepo:
        attempts = 0

        def init_schema(self):
            self.attempts += 1
            if self.attempts < 3:
                raise RepositoryError("not ready")

    schema_repo = FlakySchemaRepo()
    sleeps = []
    monkeypatch.setattr(api_main, "build_write_item_repository", lambda: schema_repo)
    monkeypatch.setattr(api_main.time, "sleep", sleeps.append)

    api_main._init_schema_with_backoff()

    assert schema_repo.attempts == 3
    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0]


def test_schema_init_gives_up_without_raising_after_the_timeout(monkeypatch):
    class DownRepo:
        def init_schema(self):
            raise RepositoryError("down")

    monkeypatch.setattr(api_main, "build_write_item_repository", lambda: DownRepo())
    monkeypatch.setattr(api_main.time, "sleep", lambda s: None)

    api_main._init_schema_with_backoff(timeout=0.0)
