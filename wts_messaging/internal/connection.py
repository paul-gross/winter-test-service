"""AMQP URL construction. The env → broker-URL translation lives here.

Mirrors ``wts_persistence.internal.engine`` for the messaging side: a single
place that resolves where to connect, defaulting sensibly for a plain local run
and deriving the per-env RabbitMQ slice when running inside a winter feature env.
"""

from __future__ import annotations

import os

_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = "5672"


def broker_url() -> str:
    """Resolve the AMQP URL for this env's RabbitMQ vhost.

    Resolution order:

    1. ``RABBITMQ_URL`` — explicit override wins outright.
    2. ``WINTER_ENV`` set — derive the per-env slice provisioned by
       ``winter provision <env>``: vhost **and** user ``wts-<env>`` on the
       shared workspace broker (host/port from ``RABBITMQ_HOST`` / ``RABBITMQ_PORT``,
       defaulting to ``localhost:5672``).
    3. Neither — fall back to the default ``/`` vhost with guest credentials so
       the worker still runs against a plain local RabbitMQ.
    """
    override = os.environ.get("RABBITMQ_URL")
    if override:
        return override

    host = os.environ.get("RABBITMQ_HOST", _DEFAULT_HOST)
    port = os.environ.get("RABBITMQ_PORT", _DEFAULT_PORT)

    env = os.environ.get("WINTER_ENV")
    if env:
        cred = f"wts-{env}"  # provisioned user == vhost name
        return f"amqp://{cred}:{cred}@{host}:{port}/{cred}"

    return f"amqp://guest:guest@{host}:{port}/"


def broker_label() -> str:
    """A credential-free 'host:port/vhost' label, safe to log."""
    env = os.environ.get("WINTER_ENV")
    host = os.environ.get("RABBITMQ_HOST", _DEFAULT_HOST)
    port = os.environ.get("RABBITMQ_PORT", _DEFAULT_PORT)
    if os.environ.get("RABBITMQ_URL"):
        return os.environ["RABBITMQ_URL"].rsplit("@", 1)[-1]
    vhost = f"wts-{env}" if env else "/"
    return f"{host}:{port}/{vhost}"
