"""Domain-level messaging errors. Callers depend on these, never on pika's."""

from __future__ import annotations


class PublishError(Exception):
    """Raised by publishers when delivering a message fails.

    Wraps the underlying pika exception at the publisher boundary so no pika
    exception type escapes into the worker or transport layers — mirrors
    ``wts_persistence.domain.errors.RepositoryError``.
    """
