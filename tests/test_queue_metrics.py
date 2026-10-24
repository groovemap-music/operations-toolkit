"""Tests for utilities/queue_metrics.py — /metrics/detailed parsing, rates, consumer join."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from utilities import queue_metrics


FIXTURE = Path(__file__).parent / "fixtures" / "rabbitmq_detailed_metrics_4.4.0.prom"


def _queue(name: str = "q", *, acked: int = 0, published: int = 0, vhost: str = "/") -> dict:
    return {"name": name, "vhost": vhost, "acked_total": acked, "published_total": published}


def test_parse_recorded_fixture() -> None:
    queues = queue_metrics.parse_detailed_metrics(FIXTURE.read_text())
    assert queues == [
        {
            "name": "groovemap-discogs-graphinator-artists",
            "vhost": "/",
            "messages": 0,
            "messages_ready": 0,
            "messages_unacknowledged": 0,
            "consumers": 1,
            "acked_total": 35,
            "published_total": 35,
        },
    ]


def test_parse_multiple_queues_and_missing_counters() -> None:
    text = "\n".join(
        [
            "# TYPE rabbitmq_detailed_queue_messages gauge",
            'rabbitmq_detailed_queue_messages{vhost="/",queue="b"} 5',
            'rabbitmq_detailed_queue_messages_ready{vhost="/",queue="b"} 4',
            'rabbitmq_detailed_queue_messages_unacked{vhost="/",queue="b"} 1',
            'rabbitmq_detailed_queue_messages{vhost="/",queue="a"} 2',
            'rabbitmq_detailed_queue_info{vhost="/",queue="a",queue_type="rabbit_classic_queue"} 1',
            'rabbitmq_other_metric{queue="a"} 99',
            'rabbitmq_detailed_queue_messages{vhost="/"} 77',
            "not a metric line",
        ],
    )
    a, b = queue_metrics.parse_detailed_metrics(text)
    assert (a["name"], a["messages"], a["published_total"], a["acked_total"]) == ("a", 2, 0, 0)
    assert (b["name"], b["messages"], b["messages_ready"], b["messages_unacknowledged"]) == ("b", 5, 4, 1)


def test_parse_sums_published_across_exchanges() -> None:
    text = "\n".join(
        [
            'rabbitmq_detailed_queue_exchange_messages_published_total{vhost="/",exchange="fx",queue="a"} 30',
            'rabbitmq_detailed_queue_exchange_messages_published_total{vhost="/",exchange="",queue="a"} 5',
            'rabbitmq_detailed_queue_exchange_messages_published_total{vhost="/",exchange="fx",queue="b"} 7',
        ],
    )
    a, b = queue_metrics.parse_detailed_metrics(text)
    assert (a["published_total"], b["published_total"]) == (35, 7)


def test_parse_empty_text() -> None:
    assert queue_metrics.parse_detailed_metrics("") == []


def test_counter_rate_two_samples() -> None:
    assert queue_metrics.counter_rate(10, 40, 5) == 6.0
    assert queue_metrics.counter_rate(10, 10, 5) == 0.0


def test_counter_rate_reset_is_unknown() -> None:
    assert queue_metrics.counter_rate(100, 3, 5) is None
    assert queue_metrics.counter_rate(1, 2, 0) is None


def test_queue_rates_only_for_queues_in_both_samples() -> None:
    previous = [_queue("a", acked=10, published=20), _queue("gone")]
    current = [_queue("a", acked=20, published=60), _queue("new", acked=1)]
    rates = queue_metrics.queue_rates(previous, current, 10)
    assert rates == {("/", "a"): {"publish": 4.0, "ack": 1.0}}


def test_queue_rates_counter_reset() -> None:
    rates = queue_metrics.queue_rates([_queue("a", acked=50, published=50)], [_queue("a", acked=2, published=60)], 5)
    assert rates[("/", "a")] == {"publish": 2.0, "ack": None}


def test_queue_pattern_uses_contract_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    assert queue_metrics.queue_pattern() == "^(?:groovemap\\-discogs|groovemap\\-musicbrainz)-"
    monkeypatch.setattr(queue_metrics, "DISCOGS_EXCHANGE_PREFIX", "staging.discogs")
    monkeypatch.setattr(queue_metrics, "MUSICBRAINZ_EXCHANGE_PREFIX", "staging-mb")
    assert queue_metrics.queue_pattern() == "^(?:staging\\.discogs|staging\\-mb)-"


def test_fetch_requests_families_and_pattern_without_credentials() -> None:
    response = MagicMock()
    response.text = FIXTURE.read_text()
    get = MagicMock(return_value=response)
    queues = queue_metrics.fetch_queue_metrics("http://prom:15692", request_get=get)
    assert len(queues) == 1
    assert get.call_args.args[0] == "http://prom:15692/metrics/detailed"
    kwargs = get.call_args.kwargs
    assert "auth" not in kwargs
    assert kwargs["timeout"] == 10
    assert ("family", "queue_exchange_metrics") in kwargs["params"]
    assert ("queue", queue_metrics.queue_pattern()) in kwargs["params"]


def test_fetch_propagates_http_error() -> None:
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("503")
    with pytest.raises(requests.HTTPError):
        queue_metrics.fetch_queue_metrics("http://prom:15692", request_get=MagicMock(return_value=response))


def test_environment_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RABBITMQ_PROMETHEUS_URL", raising=False)
    monkeypatch.delenv("RABBITMQ_SAMPLE_INTERVAL", raising=False)
    monkeypatch.delenv("RABBITMQ_CONTAINER", raising=False)
    assert queue_metrics.prometheus_url() == "http://localhost:15692"
    assert queue_metrics.sample_interval() == 5.0
    assert queue_metrics.broker_container() == "groovemap-rabbitmq"
    monkeypatch.setenv("RABBITMQ_PROMETHEUS_URL", "http://rmq:15692/")
    monkeypatch.setenv("RABBITMQ_SAMPLE_INTERVAL", "2.5")
    monkeypatch.setenv("RABBITMQ_CONTAINER", "rmq")
    assert queue_metrics.prometheus_url() == "http://rmq:15692"
    assert queue_metrics.sample_interval() == 2.5
    assert queue_metrics.broker_container() == "rmq"
    for bad in ("abc", "0", "-3"):
        monkeypatch.setenv("RABBITMQ_SAMPLE_INTERVAL", bad)
        assert queue_metrics.sample_interval() == 5.0


def test_display_endpoint_drops_credentials_and_path() -> None:
    assert queue_metrics.display_endpoint("https://user:secret@rmq.example.test:15692/x?t=1") == "https://rmq.example.test:15692"


def _ctl_run(consumers: list[dict], channels: list[dict], connections: list[dict]) -> MagicMock:
    outputs = {"list_consumers": consumers, "list_channels": channels, "list_connections": connections}

    def run(command: list[str], **_kwargs: object) -> MagicMock:
        result = MagicMock()
        result.stdout = json.dumps(outputs[command[7]])
        return result

    return MagicMock(side_effect=run)


def test_consumer_connections_joins_channel_and_connection() -> None:
    run = _ctl_run(
        [{"queue_name": "q1", "channel_pid": "ch1", "consumer_tag": "t1"}, {"queue_name": "q1", "channel_pid": "ch2", "consumer_tag": "t2"}],
        [{"pid": "ch1", "connection": "c1"}, {"pid": "ch2", "connection": "c9"}],
        [{"pid": "c1", "name": "10.0.0.1:5000 -> 10.0.0.2:5672"}],
    )
    result = queue_metrics.consumer_connections("rmq", run=run)
    assert result == {
        "q1": [
            {"consumer_tag": "t1", "connection_name": "10.0.0.1:5000 -> 10.0.0.2:5672"},
            {"consumer_tag": "t2", "connection_name": "Unknown"},
        ],
    }
    command = run.call_args_list[0].args[0]
    assert command[:3] == ["docker", "exec", "rmq"]
    assert run.call_args_list[0].kwargs["timeout"] == 60


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, "docker"),
        subprocess.TimeoutExpired("docker", 60),
        FileNotFoundError("docker"),
    ],
)
def test_consumer_connections_unavailable(error: Exception) -> None:
    assert queue_metrics.consumer_connections("rmq", run=MagicMock(side_effect=error)) is None


def test_consumer_connections_bad_output_is_unavailable() -> None:
    result = MagicMock()
    result.stdout = "not json"
    assert queue_metrics.consumer_connections("rmq", run=MagicMock(return_value=result)) is None
