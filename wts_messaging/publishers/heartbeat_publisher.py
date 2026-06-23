"""The Protocol seam for heartbeat publishing.

Consumers (the worker) depend on this Protocol, never on the pika adapter behind
it — the same convention as ``wts_persistence.repositories.item_repository``.
"""

from __future__ import annotations

from typing import Protocol


class IHeartbeatPublisher(Protocol):
    """Publishes worker heartbeats to the per-env message broker."""

    def ping(self) -> bool: ...

    def publish(self, body: dict) -> None: ...

    def close(self) -> None: ...
