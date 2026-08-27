"""Read runtime secrets without coupling operator tools to service configuration."""

from __future__ import annotations

from os import getenv
from pathlib import Path
from typing import overload


@overload
def get_secret(env_var: str, default: str) -> str: ...


@overload
def get_secret(env_var: str, default: None = None) -> str | None: ...


def get_secret(env_var: str, default: str | None = None) -> str | None:
    """Read `<VAR>_FILE` first, then `<VAR>`, without logging the value."""
    file_path = getenv(f"{env_var}_FILE")
    if file_path:
        try:
            return Path(file_path).read_text().strip()
        except OSError as exc:
            raise ValueError(f"Cannot read secret file for {env_var}: {file_path!r}") from exc
    return getenv(env_var) if default is None else getenv(env_var, default)
