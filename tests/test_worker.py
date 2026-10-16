import pytest

from worker import main as worker_main
from wts_messaging.domain.errors import PublishError
from wts_persistence.domain.errors import RepositoryError
from wts_persistence.domain.item import ItemSource


class FakePublisher:
    def __init__(self, *, ping_results=(True,), fail_ticks=()):
        self._pings = list(ping_results)
        self.fail_ticks = set(fail_ticks)
        self.published = []
        self.closed = False

    def ping(self):
        return self._pings.pop(0) if len(self._pings) > 1 else self._pings[0]

    def publish(self, body):
        if body["tick"] in self.fail_ticks:
            raise PublishError("boom")
        self.published.append(body)

    def close(self):
        self.closed = True


class FlakyRepo:
    """Records writes; raises RepositoryError for chosen labels."""

    def __init__(self, *, ping_results=(True,), fail_labels=()):
        self._pings = list(ping_results)
        self.fail_labels = set(fail_labels)
        self.added = []

    def ping(self):
        return self._pings.pop(0) if len(self._pings) > 1 else self._pings[0]

    def add_item(self, label, source):
        if label in self.fail_labels:
            raise RepositoryError("db down")
        self.added.append((label, source))


@pytest.fixture
def sleeps(monkeypatch):
    calls = []
    monkeypatch.setattr(worker_main.time, "sleep", calls.append)
    return calls


def test_config_reads_env_with_defaults(monkeypatch):
    monkeypatch.delenv("WTS_WORKER_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("WTS_WORKER_CRASH_AFTER", raising=False)
    assert worker_main._interval() == 2.0
    assert worker_main._crash_after() == 0

    monkeypatch.setenv("WTS_WORKER_INTERVAL_SECONDS", "0.5")
    monkeypatch.setenv("WTS_WORKER_CRASH_AFTER", "7")
    assert worker_main._interval() == 0.5
    assert worker_main._crash_after() == 7


def test_wait_for_db_backs_off_exponentially_until_ready(sleeps):
    repo = FlakyRepo(ping_results=(False, False, False, True))

    worker_main._wait_for_db(repo)

    assert sleeps == [1.0, 2.0, 4.0]


def test_wait_for_db_exits_with_code_1_when_deadline_passes(sleeps):
    with pytest.raises(SystemExit) as excinfo:
        worker_main._wait_for_db(FlakyRepo(ping_results=(False,)), timeout=0.0)

    assert excinfo.value.code == 1
    assert sleeps == []


def test_wait_for_broker_is_a_soft_dependency(sleeps):
    reached = worker_main._wait_for_broker(
        FakePublisher(ping_results=(False,)), timeout=0.0
    )

    assert reached is False


def test_wait_for_broker_returns_true_once_reachable(sleeps):
    reached = worker_main._wait_for_broker(
        FakePublisher(ping_results=(False, True))
    )

    assert reached is True
    assert sleeps == [1.0]


def _run_main(monkeypatch, repo, publisher, *, crash_after):
    monkeypatch.setenv("WTS_WORKER_CRASH_AFTER", str(crash_after))
    monkeypatch.setenv("WINTER_ENV", "beta")
    monkeypatch.setattr(worker_main, "create_db_engine", lambda: object())
    monkeypatch.setattr(worker_main, "WriteItemRepository", lambda engine: repo)
    monkeypatch.setattr(worker_main, "AmqpHeartbeatPublisher", lambda: publisher)
    with pytest.raises(SystemExit) as excinfo:
        worker_main.main()
    return excinfo.value.code


def test_main_writes_and_publishes_each_tick_then_exits_at_crash_after(
    monkeypatch, sleeps
):
    repo, publisher = FlakyRepo(), FakePublisher()

    code = _run_main(monkeypatch, repo, publisher, crash_after=3)

    assert code == 1
    assert repo.added == [(f"heartbeat {n}", ItemSource.WORKER) for n in (1, 2, 3)]
    assert publisher.published == [
        {"env": "beta", "tick": n, "label": f"heartbeat {n}"} for n in (1, 2, 3)
    ]
    assert publisher.closed is True
    assert len(sleeps) == 2  # no sleep after the crashing tick


def test_main_tolerates_db_and_broker_failures_and_keeps_ticking(monkeypatch, sleeps):
    repo = FlakyRepo(fail_labels={"heartbeat 1"})
    publisher = FakePublisher(fail_ticks={2})

    code = _run_main(monkeypatch, repo, publisher, crash_after=3)

    assert code == 1
    assert [label for label, _ in repo.added] == ["heartbeat 2", "heartbeat 3"]
    assert [b["tick"] for b in publisher.published] == [1, 3]
