"""Private transport primitives shared by observational commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Callable


def rabbitmq_queues(
    request_get: Callable[..., Any],
    base_url: str,
    username: str,
    password: str,
) -> list[dict[str, Any]]:
    """Fetch the unmodified RabbitMQ management queue payload."""
    response = request_get(f"{base_url}/api/queues", auth=(username, password), timeout=10)
    response.raise_for_status()
    data: list[dict[str, Any]] = response.json()
    return data


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
