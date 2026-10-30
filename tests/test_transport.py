"""Tests for utilities/_transport.py — the missing-Docker-CLI path."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from utilities._transport import DockerUnavailableError, docker_compose_output, docker_exec_output, docker_run


if TYPE_CHECKING:
    from collections.abc import Callable


def _raising(error: OSError) -> MagicMock:
    return MagicMock(side_effect=error)


def test_docker_run_prefixes_docker_binary() -> None:
    run = MagicMock(return_value="ok")
    assert docker_run(run, ["ps"], timeout=1) == "ok"
    run.assert_called_once_with(["docker", "ps"], timeout=1)


def test_missing_cli_is_reported_as_docker_unavailable() -> None:
    with pytest.raises(DockerUnavailableError, match="Docker CLI not found on PATH"):
        docker_run(_raising(FileNotFoundError(2, "No such file", "docker")), ["ps"])


def test_unexecutable_cli_is_reported_as_docker_unavailable() -> None:
    with pytest.raises(DockerUnavailableError, match="not executable"):
        docker_run(_raising(PermissionError(13, "Permission denied", "docker")), ["ps"])


@pytest.mark.parametrize(
    "call",
    [
        lambda run: docker_exec_output(run, "container", "true"),
        lambda run: docker_compose_output(run, "ps"),
    ],
)
def test_output_helpers_surface_missing_cli(call: Callable[[MagicMock], str]) -> None:
    with pytest.raises(DockerUnavailableError, match="Docker CLI not found on PATH"):
        call(_raising(FileNotFoundError("docker")))
