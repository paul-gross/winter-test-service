"""pika AMQP publisher. All pika usage is confined to this file."""

from __future__ import annotations

import json
import logging

import pika
from pika.exceptions import AMQPError

from wts_messaging.domain.errors import PublishError
from wts_messaging.internal.connection import broker_url
from wts_messaging.publishers.heartbeat_publisher import IHeartbeatPublisher

logger = logging.getLogger(__name__)

# Durable queue the worker publishes heartbeats to. Declared on first use so the
# queue exists in the per-env vhost without any out-of-band setup.
QUEUE = "heartbeats"


class AmqpHeartbeatPublisher:
    """BlockingConnection publisher for worker heartbeats.

    Lazily (re)connects: a dropped connection or a not-yet-provisioned vhost
    surfaces as a ``PublishError`` on ``publish`` (or ``False`` from ``ping``)
    and resets internal state, so the next call reconnects cleanly. This keeps a
    broker blip from permanently wedging the worker — mirroring the pooled
    engine's ``pool_pre_ping`` recovery on the persistence side.
    """

    def __init__(self, url: str | None = None) -> None:
        self._url = url or broker_url()
        self._conn: pika.BlockingConnection | None = None
        self._channel = None

    def _ensure_channel(self):
        if (
            self._conn is not None
            and self._conn.is_open
            and self._channel is not None
            and self._channel.is_open
        ):
            return self._channel
        self._conn = pika.BlockingConnection(pika.URLParameters(self._url))
        self._channel = self._conn.channel()
        self._channel.queue_declare(queue=QUEUE, durable=True)
        return self._channel

    def ping(self) -> bool:
        try:
            self._ensure_channel()
            return True
        except (AMQPError, OSError) as exc:
            logger.warning("broker not reachable: %s", exc)
            self._reset()
            return False

    def publish(self, body: dict) -> None:
        try:
            channel = self._ensure_channel()
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE,
                body=json.dumps(body).encode(),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,  # persistent
                ),
            )
        except (AMQPError, OSError) as exc:
            self._reset()
            raise self._wrap(exc, "failed to publish heartbeat")

    def close(self) -> None:
        if self._conn is not None and self._conn.is_open:
            try:
                self._conn.close()
            except (AMQPError, OSError):
                pass
        self._reset()

    def _reset(self) -> None:
        self._channel = None
        self._conn = None

    @staticmethod
    def _wrap(exc: Exception, message: str) -> PublishError:
        # Log once at the wrap site so callers never re-log the library error.
        logger.warning("%s: %s", message, exc)
        return PublishError(message)


# Typecheck-time conformance sentinel: pin the adapter to its Protocol seam.
def _conforms_heartbeat_publisher(x: AmqpHeartbeatPublisher) -> IHeartbeatPublisher:
    return x
