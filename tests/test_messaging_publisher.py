import json
from typing import ClassVar

import pika
import pytest
from pika.exceptions import AMQPConnectionError

from wts_messaging.domain.errors import PublishError
from wts_messaging.internal import amqp_publisher
from wts_messaging.internal.amqp_publisher import QUEUE, AmqpHeartbeatPublisher


class FakeChannel:
    def __init__(self, conn):
        self.conn = conn
        self.is_open = True
        self.declared = []
        self.published = []

    def queue_declare(self, queue, durable):
        self.declared.append((queue, durable))

    def basic_publish(self, exchange, routing_key, body, properties):
        if self.conn.fail_publish:
            raise AMQPConnectionError("connection reset")
        self.published.append((exchange, routing_key, body, properties))


class FakeConnection:
    """Stands in for pika.BlockingConnection; records every instance created."""

    instances: ClassVar[list["FakeConnection"]] = []
    refuse = False

    def __init__(self, params):
        if FakeConnection.refuse:
            raise AMQPConnectionError("refused")
        self.params = params
        self.is_open = True
        self.fail_publish = False
        self.channels = []
        FakeConnection.instances.append(self)

    def channel(self):
        ch = FakeChannel(self)
        self.channels.append(ch)
        return ch

    def close(self):
        self.is_open = False


@pytest.fixture(autouse=True)
def fake_pika(monkeypatch):
    FakeConnection.instances = []
    FakeConnection.refuse = False
    monkeypatch.setattr(amqp_publisher.pika, "BlockingConnection", FakeConnection)


URL = "amqp://guest:guest@localhost:5672/"


def test_publish_sends_persistent_json_to_the_durable_heartbeats_queue():
    pub = AmqpHeartbeatPublisher(URL)

    pub.publish({"env": "beta", "tick": 3, "label": "heartbeat 3"})

    channel = FakeConnection.instances[0].channels[0]
    assert channel.declared == [(QUEUE, True)]
    exchange, routing_key, body, props = channel.published[0]
    assert (exchange, routing_key) == ("", "heartbeats")
    assert json.loads(body) == {"env": "beta", "tick": 3, "label": "heartbeat 3"}
    assert props.delivery_mode == 2
    assert props.content_type == "application/json"
    assert FakeConnection.instances[0].params.host == "localhost"


def test_connection_is_reused_across_publishes():
    pub = AmqpHeartbeatPublisher(URL)

    pub.publish({"tick": 1})
    pub.publish({"tick": 2})

    assert len(FakeConnection.instances) == 1
    assert len(FakeConnection.instances[0].channels[0].published) == 2


def test_failed_publish_raises_domain_error_then_reconnects_next_call():
    pub = AmqpHeartbeatPublisher(URL)
    pub.publish({"tick": 1})
    FakeConnection.instances[0].fail_publish = True

    with pytest.raises(PublishError):
        pub.publish({"tick": 2})

    pub.publish({"tick": 3})
    assert len(FakeConnection.instances) == 2
    assert len(FakeConnection.instances[1].channels[0].published) == 1


def test_ping_reflects_broker_reachability():
    pub = AmqpHeartbeatPublisher(URL)
    FakeConnection.refuse = True
    assert pub.ping() is False

    FakeConnection.refuse = False
    assert pub.ping() is True


def test_publish_when_broker_unreachable_raises_publish_error_not_pika_error():
    FakeConnection.refuse = True

    with pytest.raises(PublishError) as excinfo:
        AmqpHeartbeatPublisher(URL).publish({"tick": 1})

    assert not isinstance(excinfo.value, pika.exceptions.AMQPError)


def test_close_closes_connection_and_next_publish_reconnects():
    pub = AmqpHeartbeatPublisher(URL)
    pub.publish({"tick": 1})

    pub.close()
    assert FakeConnection.instances[0].is_open is False

    pub.publish({"tick": 2})
    assert len(FakeConnection.instances) == 2


def test_url_defaults_to_resolved_broker_url(monkeypatch):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://a:b@example:1234/vh")

    AmqpHeartbeatPublisher().ping()

    params = FakeConnection.instances[0].params
    assert (params.host, params.port, params.virtual_host) == ("example", 1234, "vh")
