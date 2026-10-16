import pytest

from wts_messaging.internal.connection import broker_label, broker_url

ENV_VARS = ("RABBITMQ_URL", "RABBITMQ_HOST", "RABBITMQ_PORT", "WINTER_ENV")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_plain_local_run_uses_default_vhost_and_guest(monkeypatch):
    assert broker_url() == "amqp://guest:guest@localhost:5672/"
    assert broker_label() == "localhost:5672//"


def test_winter_env_derives_per_env_vhost_and_user(monkeypatch):
    monkeypatch.setenv("WINTER_ENV", "beta")
    monkeypatch.setenv("RABBITMQ_HOST", "broker")
    monkeypatch.setenv("RABBITMQ_PORT", "5999")

    assert broker_url() == "amqp://wts-beta:wts-beta@broker:5999/wts-beta"
    assert broker_label() == "broker:5999/wts-beta"


def test_explicit_url_overrides_derivation(monkeypatch):
    monkeypatch.setenv("WINTER_ENV", "beta")
    monkeypatch.setenv("RABBITMQ_URL", "amqp://u:secret@h:1/v")

    assert broker_url() == "amqp://u:secret@h:1/v"


def test_label_never_leaks_credentials_from_explicit_url(monkeypatch):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://u:secret@h:1/v")

    assert broker_label() == "h:1/v"
    assert "secret" not in broker_label()
