"""Queue counts, rates, and consumer connections without management statistics.

Counts and counters come from the rabbitmq_prometheus ``/metrics/detailed`` endpoint
(ADR 0017). Consumer connection names are not exposed there, and the management API
returns neither them nor ``message_stats`` once metrics collection is disabled, so they are
joined from ``rabbitmqctl`` inside the broker container (verified on RabbitMQ 4.4.0).
"""

from __future__ import annotations

import json
import os
import re
import subprocess  # nosec B404
from typing import Any
from urllib.parse import urlsplit

import requests

from utilities._transport import docker_exec_output, rabbitmq_detailed_metrics
from utilities.catalog_contract import DISCOGS_EXCHANGE_PREFIX, MUSICBRAINZ_EXCHANGE_PREFIX


DEFAULT_PROMETHEUS_URL = "http://localhost:15692"
DEFAULT_CONTAINER = "groovemap-rabbitmq"
DEFAULT_SAMPLE_INTERVAL = 5.0

_GAUGES = {
    "rabbitmq_detailed_queue_messages": "messages",
    "rabbitmq_detailed_queue_messages_ready": "messages_ready",
    "rabbitmq_detailed_queue_messages_unacked": "messages_unacknowledged",
    "rabbitmq_detailed_queue_consumers": "consumers",
    "rabbitmq_detailed_queue_messages_acked_total": "acked_total",
    "rabbitmq_detailed_queue_exchange_messages_published_total": "published_total",
}
_SAMPLE_LINE = re.compile(r"^([A-Za-z_:][A-Za-z0-9_:]*)\{(.*)\}\s+(\S+)\s*$")
_LABEL = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')


def prometheus_url() -> str:
    """Return the rabbitmq_prometheus base URL (no credentials are needed or sent)."""
    return os.environ.get("RABBITMQ_PROMETHEUS_URL", DEFAULT_PROMETHEUS_URL).rstrip("/")


def broker_container() -> str:
    """Return the broker container used for the consumer-connection lookup."""
    return os.environ.get("RABBITMQ_CONTAINER", DEFAULT_CONTAINER)


def sample_interval() -> float:
    """Return the seconds between the two samples used for rates; invalid values use the default."""
    try:
        value = float(os.environ.get("RABBITMQ_SAMPLE_INTERVAL", DEFAULT_SAMPLE_INTERVAL))
    except ValueError:
        return DEFAULT_SAMPLE_INTERVAL
    return value if value > 0 else DEFAULT_SAMPLE_INTERVAL


def queue_pattern() -> str:
    """Build the queue regex from the contract prefixes, honoring environment overrides."""
    prefixes = "|".join(re.escape(prefix) for prefix in (DISCOGS_EXCHANGE_PREFIX, MUSICBRAINZ_EXCHANGE_PREFIX))
    return f"^(?:{prefixes})-"


def display_endpoint(url: str) -> str:
    """Return scheme://host[:port] only, so a URL that embeds credentials is never printed."""
    parts = urlsplit(url)
    host = parts.hostname or "unknown"
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{host}{port}"


def parse_detailed_metrics(text: str) -> list[dict[str, Any]]:
    """Parse /metrics/detailed exposition text into one dict per queue, sorted by name.

    Keys mirror the management payload (``name``, ``messages``, ``messages_ready``,
    ``messages_unacknowledged``, ``consumers``) plus ``vhost`` and the cumulative
    ``acked_total`` / ``published_total`` counters. A series the broker has not emitted yet
    (a counter appears with the first publish or ack) is reported as 0.
    """
    queues: dict[tuple[str, str], dict[str, Any]] = {}
    for line in text.splitlines():
        match = _SAMPLE_LINE.match(line)
        if match is None or match.group(1) not in _GAUGES:
            continue
        labels = dict(_LABEL.findall(match.group(2)))
        if "queue" not in labels:
            continue
        key = (labels.get("vhost", ""), labels["queue"])
        queue = queues.setdefault(
            key,
            {
                "name": key[1],
                "vhost": key[0],
                "messages": 0,
                "messages_ready": 0,
                "messages_unacknowledged": 0,
                "consumers": 0,
                "acked_total": 0,
                "published_total": 0,
            },
        )
        queue[_GAUGES[match.group(1)]] = int(float(match.group(3)))
    return sorted(queues.values(), key=lambda q: (q["name"], q["vhost"]))


def fetch_queue_metrics(
    base_url: str | None = None,
    *,
    request_get: Any = requests.get,
) -> list[dict[str, Any]]:
    """Fetch and parse the current per-queue metrics; raises requests exceptions on failure."""
    text = rabbitmq_detailed_metrics(request_get, base_url or prometheus_url(), queue_pattern())
    return parse_detailed_metrics(text)


def counter_rate(previous: int, current: int, seconds: float) -> float | None:
    """Return messages/second between two counter samples, or None when it cannot be known.

    A decrease means the broker restarted or the queue was recreated between samples, so
    the interval has no meaningful rate.
    """
    if seconds <= 0 or current < previous:
        return None
    return (current - previous) / seconds


def queue_rates(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
    seconds: float,
) -> dict[tuple[str, str], dict[str, float | None]]:
    """Compute publish and ack rates for queues present in both samples."""
    before = {(q["vhost"], q["name"]): q for q in previous}
    rates: dict[tuple[str, str], dict[str, float | None]] = {}
    for queue in current:
        key = (queue["vhost"], queue["name"])
        if key not in before:
            continue
        rates[key] = {
            "publish": counter_rate(before[key]["published_total"], queue["published_total"], seconds),
            "ack": counter_rate(before[key]["acked_total"], queue["acked_total"], seconds),
        }
    return rates


def consumer_connections(
    container: str | None = None,
    *,
    run: Any = subprocess.run,
) -> dict[str, list[dict[str, str]]] | None:
    """Map queue name to its consumers' tags and connection names, or None if unavailable.

    Joins ``list_consumers`` (queue, channel pid, tag) with ``list_channels`` (channel pid,
    connection pid) and ``list_connections`` (connection pid, name). All three read broker
    state directly and need no credentials.
    """
    container = container or broker_container()
    try:
        consumers = _ctl_json(run, container, "list_consumers", "queue_name", "channel_pid", "consumer_tag")
        channels = _ctl_json(run, container, "list_channels", "pid", "connection")
        connections = _ctl_json(run, container, "list_connections", "pid", "name")
    except subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError, KeyError, TypeError:
        return None
    connection_of_channel = {row["pid"]: row["connection"] for row in channels}
    name_of_connection = {row["pid"]: row["name"] for row in connections}
    result: dict[str, list[dict[str, str]]] = {}
    for row in consumers:
        connection = connection_of_channel.get(row["channel_pid"], "")
        result.setdefault(row["queue_name"], []).append(
            {"consumer_tag": row["consumer_tag"], "connection_name": name_of_connection.get(connection, "Unknown")},
        )
    return result


def _ctl_json(run: Any, container: str, command: str, *columns: str) -> list[dict[str, Any]]:
    output = docker_exec_output(run, container, "rabbitmqctl", "--quiet", "--formatter", "json", command, *columns)
    rows: list[dict[str, Any]] = json.loads(output)
    return rows
