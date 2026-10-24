"""Tests for utilities/monitor_queues.py — the real-time queue monitor."""

from __future__ import annotations

from unittest.mock import patch

import requests

from utilities import monitor_queues


def _q(name: str, ready: int, unacked: int, total: int, *, acked: int = 0, published: int = 0) -> dict:
    return {
        "name": name,
        "vhost": "/",
        "messages_ready": ready,
        "messages_unacknowledged": unacked,
        "messages": total,
        "acked_total": acked,
        "published_total": published,
    }


def test_get_queue_stats_success() -> None:
    payload = [_q("groovemap-discogs-graphinator-artists", 0, 0, 0)]
    with patch.object(monitor_queues.queue_metrics, "fetch_queue_metrics", return_value=payload) as fetch:
        assert monitor_queues.get_queue_stats(base_url="http://prom:15692") == payload
    fetch.assert_called_once_with("http://prom:15692")


def test_get_queue_stats_request_error_hides_credentials(capsys) -> None:
    with patch.object(monitor_queues.queue_metrics, "fetch_queue_metrics", side_effect=requests.RequestException("down")):
        assert monitor_queues.get_queue_stats(base_url="http://user:secret@prom.example.test:15692") is None
    out = capsys.readouterr().out
    assert "Error connecting to RabbitMQ Prometheus endpoint at http://prom.example.test:15692" in out
    assert "secret" not in out


def test_monitor_queues_renders_then_stops(capsys) -> None:
    payload = [
        _q("groovemap-discogs-graphinator-artists", 4, 2, 6),
        _q("groovemap-musicbrainz-tableinator-releases", 1, 0, 1),
    ]
    with (
        patch.object(monitor_queues, "get_queue_stats", return_value=payload),
        patch.object(monitor_queues.time, "sleep", side_effect=KeyboardInterrupt),
        patch.object(monitor_queues.time, "strftime", return_value="2026-01-01 00:00:00"),
    ):
        monitor_queues.monitor_queues(interval=1)

    out = capsys.readouterr().out
    assert "graphinator-artists" in out
    assert "tableinator-releases" in out
    assert "Total messages across all queues: 7" in out
    assert "Monitoring stopped." in out


def test_monitor_queues_computes_rates_from_consecutive_refreshes(capsys) -> None:
    name = "groovemap-discogs-graphinator-artists"
    samples = [[_q(name, 0, 0, 0, acked=10, published=10)], [_q(name, 0, 0, 0, acked=30, published=70)]]
    with (
        patch.object(monitor_queues, "get_queue_stats", side_effect=[*samples, KeyboardInterrupt]),
        patch.object(monitor_queues.time, "sleep", return_value=None),
        patch.object(monitor_queues.time, "monotonic", side_effect=[0.0, 10.0]),
    ):
        monitor_queues.monitor_queues(interval=1)

    first, second = capsys.readouterr().out.split("RabbitMQ Queue Monitor")[1:3]
    assert f"{name:<50} 0          0          0          -        -" in first
    assert "6.00     2.00" in second


def test_monitor_queues_counter_reset_shows_no_rate(capsys) -> None:
    name = "groovemap-discogs-graphinator-artists"
    samples = [[_q(name, 0, 0, 0, acked=50, published=50)], [_q(name, 0, 0, 0, acked=1, published=1)]]
    with (
        patch.object(monitor_queues, "get_queue_stats", side_effect=[*samples, KeyboardInterrupt]),
        patch.object(monitor_queues.time, "sleep", return_value=None),
        patch.object(monitor_queues.time, "monotonic", side_effect=[0.0, 5.0]),
    ):
        monitor_queues.monitor_queues(interval=1)

    second = capsys.readouterr().out.split("RabbitMQ Queue Monitor")[2]
    assert "-        -" in second


def test_monitor_queues_handles_empty_fetch(capsys) -> None:
    # First loop: no data -> "Failed to fetch" -> sleep -> continue; second loop
    # interrupts. Sleep is a no-op so the ``continue`` branch is exercised.
    with (
        patch.object(monitor_queues, "get_queue_stats", side_effect=[None, KeyboardInterrupt]),
        patch.object(monitor_queues.time, "sleep", return_value=None),
    ):
        monitor_queues.monitor_queues(interval=1)
    out = capsys.readouterr().out
    assert "Failed to fetch queue data" in out
    assert "Monitoring stopped." in out


def test_monitor_queues_empty_list_is_not_a_fetch_failure(capsys) -> None:
    """An empty queue list is a successful broker response, not a fetch failure.

    A successful HTTP 200 with no queues declared yet (e.g. right after `just up`,
    before the extractor/consumers connect) — it must not print the same
    "Failed to fetch queue data" message as a genuine RequestException (None).
    """
    with (
        patch.object(monitor_queues, "get_queue_stats", side_effect=[[], KeyboardInterrupt]),
        patch.object(monitor_queues.time, "sleep", return_value=None),
    ):
        monitor_queues.monitor_queues(interval=1)
    out = capsys.readouterr().out
    assert "Failed to fetch queue data" not in out
    assert "No queues declared yet" in out
    assert "Monitoring stopped." in out


def test_main_passes_interval_argument(monkeypatch) -> None:
    monkeypatch.setattr(monitor_queues.sys, "argv", ["groovemap-monitor-queues", "10"])
    with patch.object(monitor_queues, "monitor_queues") as monitor:
        monitor_queues.main()
    monitor.assert_called_once_with(10)
