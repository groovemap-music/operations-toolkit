"""Private transport primitives shared by observational commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Callable


DETAILED_METRIC_FAMILIES = (
    "queue_coarse_metrics",
    "queue_consumer_count",
    "queue_delivery_metrics",
    "queue_exchange_metrics",
)


def rabbitmq_detailed_metrics(
    request_get: Callable[..., Any],
    base_url: str,
    queue_pattern: str,
) -> str:
    """Fetch the unauthenticated rabbitmq_prometheus per-queue families as exposition text."""
    response = request_get(
        f"{base_url}/metrics/detailed",
        params=[("family", family) for family in DETAILED_METRIC_FAMILIES] + [("queue", queue_pattern)],
        timeout=10,
    )
    response.raise_for_status()
    text: str = response.text
    return text


def docker_exec_output(
    run: Callable[..., Any],
    container: str,
    *arguments: str,
) -> str:
    """Run one bounded command inside a named container and return stdout."""
    result = run(
        ["docker", "exec", container, *arguments],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    output: str = result.stdout
    return output


def docker_compose_output(
    run: Callable[..., Any],
    *arguments: str,
) -> str:
    """Run one bounded Docker Compose observation and return stdout."""
    result = run(
        ["docker", "compose", *arguments],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    output: str = result.stdout
    return output
