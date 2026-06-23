"""Background worker: writes heartbeat rows via the shared persistence layer."""

import logging
import os
import sys
import time

from wts_logging import configure_logging
from wts_messaging.domain.errors import PublishError
from wts_messaging.internal.amqp_publisher import AmqpHeartbeatPublisher
from wts_messaging.internal.connection import broker_label
from wts_messaging.publishers.heartbeat_publisher import IHeartbeatPublisher
from wts_persistence.domain.errors import RepositoryError
from wts_persistence.domain.item import ItemSource
from wts_persistence.internal.engine import create_db_engine
from wts_persistence.internal.item_repository import WriteItemRepository
from wts_persistence.repositories.item_repository import IWriteItemRepository

# ---------------------------------------------------------------------------
# Logging: INFO → stdout, WARNING+ → stderr (shared with the api)
# ---------------------------------------------------------------------------

configure_logging()
logger = logging.getLogger("worker")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _interval() -> float:
    return float(os.environ.get("WTS_WORKER_INTERVAL_SECONDS", "2"))


def _crash_after() -> int:
    return int(os.environ.get("WTS_WORKER_CRASH_AFTER", "0"))


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def _wait_for_db(repo: IWriteItemRepository, timeout: float = 60.0) -> None:
    """Block until the DB answers a ping, with capped exponential backoff."""
    deadline = time.monotonic() + timeout
    attempt = 0
    while not repo.ping():
        attempt += 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.error("DB not reachable after %d attempts — exiting", attempt)
            sys.exit(1)
        wait = min(2.0 ** (attempt - 1), 8.0, remaining)
        logger.info("DB not ready (attempt %d) — retrying in %.1fs", attempt, wait)
        time.sleep(wait)
    logger.info("Connected to DB")


def _wait_for_broker(publisher: IHeartbeatPublisher, timeout: float = 30.0) -> bool:
    """Try to reach the broker, with capped exponential backoff.

    Unlike the DB (a hard dependency that exits on failure), the broker is a
    soft dependency: if it never answers within ``timeout`` we log and return
    ``False`` so the worker still runs its DB heartbeats. Per-tick publishes
    keep retrying, so an un-provisioned vhost shows up as recurring warnings
    rather than a dead worker.
    """
    deadline = time.monotonic() + timeout
    attempt = 0
    while not publisher.ping():
        attempt += 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.warning(
                "broker (%s) not reachable after %d attempts — continuing; "
                "publishes will retry per tick (is the vhost provisioned?)",
                broker_label(), attempt,
            )
            return False
        wait = min(2.0 ** (attempt - 1), 8.0, remaining)
        logger.info("broker not ready (attempt %d) — retrying in %.1fs", attempt, wait)
        time.sleep(wait)
    logger.info("Connected to broker (%s)", broker_label())
    return True


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    interval = _interval()
    crash_after = _crash_after()

    logger.info(
        "Starting worker (interval=%.1fs, crash_after=%d)", interval, crash_after
    )

    repo: IWriteItemRepository = WriteItemRepository(create_db_engine())
    _wait_for_db(repo)

    publisher: IHeartbeatPublisher = AmqpHeartbeatPublisher()
    _wait_for_broker(publisher)

    tick = 0
    while True:
        tick += 1
        label = f"heartbeat {tick}"

        try:
            repo.add_item(label, ItemSource.WORKER)
            logger.info("tick %d: wrote '%s'", tick, label)
        except RepositoryError as exc:
            # Tolerate transient DB issues (e.g. the api hasn't created the
            # schema yet) without crashing — the pooled engine reconnects, so
            # we just retry on the next tick.
            logger.warning(
                "DB write failed on tick %d: %s — will retry next tick", tick, exc
            )

        # Publish the heartbeat to this env's RabbitMQ vhost. Tolerate broker
        # issues the same way as DB writes — the publisher reconnects, so we
        # just retry on the next tick.
        try:
            publisher.publish({"env": os.environ.get("WINTER_ENV"), "tick": tick, "label": label})
            logger.info("tick %d: published heartbeat", tick)
        except PublishError as exc:
            logger.warning(
                "publish failed on tick %d: %s — will retry next tick", tick, exc
            )

        # Every 5th tick emit a periodic warning to stderr.
        if tick % 5 == 0:
            logger.warning("periodic heartbeat warn at tick %d", tick)

        if crash_after > 0 and tick >= crash_after:
            logger.warning(
                "WTS_WORKER_CRASH_AFTER=%d reached at tick %d — exiting with code 1",
                crash_after, tick,
            )
            publisher.close()
            sys.exit(1)

        time.sleep(interval)


if __name__ == "__main__":
    main()
