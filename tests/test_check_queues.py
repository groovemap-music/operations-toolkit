"""Tests for utilities/check_queues.py — the RabbitMQ consumer-queue reporter."""

from __future__ import annotations

from unittest.mock import patch

import requests

from utilities import check_queues, queue_metrics


def _queue(name: str, *, consumers: int = 0, acked: int = 0, published: int = 0) -> dict:
    return {
        "name": name,
        "vhost": "/",
        "messages": 10,
        "messages_ready": 7,
        "messages_unacknowledged": 3,
        "consumers": consumers,
        "acked_total": acked,
        "published_total": published,
    }


def _run(first: list[dict], second: list[dict], connections=None):
    patches = (
        patch.object(check_queues.queue_metrics, "fetch_queue_metrics", side_effect=[first, second]),
        patch.object(check_queues.queue_metrics, "consumer_connections", return_value=connections),
        patch.object(check_queues.time, "sleep"),
        patch.object(check_queues.time, "monotonic", side_effect=[100.0, 110.0]),
    )
    return patches


def _check(first, second, connections=None):
    p1, p2, p3, p4 = _run(first, second, connections)
    with p1 as fetch, p2, p3 as sleep, p4:
        check_queues.check_rabbitmq_queues()
    return fetch, sleep


def test_renders_consumer_queues_with_rates_and_connections(capsys) -> None:
    name = "groovemap-discogs-graphinator-artists"
    first = [_queue(name, consumers=1, acked=0, published=0)]
    second = [_queue(name, consumers=1, acked=15, published=25)]
    connections = {name: [{"consumer_tag": "ctag-1", "connection_name": "conn-1"}]}
    fetch, sleep = _check(first, second, connections)

    out = capsys.readouterr().out
    assert f"Queue: {name}" in out
    assert "Total Messages: 10" in out
    assert "Ready Messages: 7" in out
    assert "Unacked Messages: 3" in out
    assert "Active Consumers: 1" in out
    assert "Ack Rate: 1.50 msg/s" in out
    assert "Publish Rate: 2.50 msg/s" in out
    assert "ctag-1" in out
    assert "conn-1" in out
    assert fetch.call_count == 2
    sleep.assert_called_once_with(queue_metrics.sample_interval())


def test_counter_reset_prints_unknown_rate(capsys) -> None:
    name = "groovemap-discogs-graphinator-artists"
    _check([_queue(name, acked=50, published=50)], [_queue(name, acked=1, published=60)])
    out = capsys.readouterr().out
    assert "Ack Rate: n/a" in out
    assert "Publish Rate: 1.00 msg/s" in out


def test_consumer_lookup_unavailable_is_reported(capsys) -> None:
    name = "groovemap-discogs-graphinator-artists"
    _check([_queue(name, consumers=1)], [_queue(name, consumers=1)], connections=None)
    out = capsys.readouterr().out
    assert "Consumer Details:" in out
    assert "Unavailable" in out


def test_no_consumer_queues(capsys) -> None:
    with patch.object(check_queues.queue_metrics, "fetch_queue_metrics", return_value=[]) as fetch:
        check_queues.check_rabbitmq_queues()
    assert "No consumer queues found!" in capsys.readouterr().out
    assert fetch.call_count == 1


def test_queue_without_consumers_omits_details(capsys) -> None:
    name = "groovemap-discogs-tableinator-artists"
    _check([_queue(name)], [_queue(name)])
    out = capsys.readouterr().out
    assert "tableinator" in out
    assert "Consumer Details" not in out


def test_connection_error_reports_endpoint_without_credentials(capsys, monkeypatch) -> None:
    monkeypatch.setenv("RABBITMQ_PROMETHEUS_URL", "http://user:secret@rmq.example.test:15692")
    with patch.object(check_queues.queue_metrics, "fetch_queue_metrics", side_effect=requests.ConnectionError("boom")):
        check_queues.check_rabbitmq_queues()
    out = capsys.readouterr().out
    assert "Could not connect to RabbitMQ Prometheus endpoint at http://rmq.example.test:15692" in out
    assert "secret" not in out
    assert "rabbitmq_prometheus" in out


def test_http_error_reports_status(capsys) -> None:
    response = requests.Response()
    response.status_code = 503
    with patch.object(check_queues.queue_metrics, "fetch_queue_metrics", side_effect=requests.HTTPError(response=response)):
        check_queues.check_rabbitmq_queues()
    assert "HTTP 503 from RabbitMQ Prometheus endpoint" in capsys.readouterr().out


def test_http_error_without_response(capsys) -> None:
    with patch.object(check_queues.queue_metrics, "fetch_queue_metrics", side_effect=requests.HTTPError()):
        check_queues.check_rabbitmq_queues()
    assert "HTTP unknown from RabbitMQ Prometheus endpoint" in capsys.readouterr().out


def test_unexpected_error(capsys) -> None:
    with patch.object(check_queues.queue_metrics, "fetch_queue_metrics", side_effect=RuntimeError("kaput")):
        check_queues.check_rabbitmq_queues()
    assert "Unexpected error: kaput" in capsys.readouterr().out


def test_queues_vanish_between_samples(capsys) -> None:
    _check([_queue("groovemap-discogs-graphinator-artists")], [])
    assert "No consumer queues found!" in capsys.readouterr().out
