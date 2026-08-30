"""Tests for secret-file and environment lookup precedence."""

from typing import TYPE_CHECKING

import pytest

from utilities.secrets import get_secret


if TYPE_CHECKING:
    from pathlib import Path


def test_file_value_takes_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret_file = tmp_path / "password"
    secret_file.write_text("from-file\n")
    monkeypatch.setenv("EXAMPLE_SECRET", "from-env")
    monkeypatch.setenv("EXAMPLE_SECRET_FILE", str(secret_file))
    assert get_secret("EXAMPLE_SECRET") == "from-file"


def test_environment_and_default_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXAMPLE_SECRET_FILE", raising=False)
    monkeypatch.setenv("EXAMPLE_SECRET", "from-env")
    assert get_secret("EXAMPLE_SECRET") == "from-env"
    monkeypatch.delenv("EXAMPLE_SECRET", raising=False)
    assert get_secret("EXAMPLE_SECRET", "fallback") == "fallback"


def test_unreadable_file_does_not_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMPLE_SECRET", "must-not-be-used")
    monkeypatch.setenv("EXAMPLE_SECRET_FILE", "/path/that/does/not/exist")
    with pytest.raises(ValueError, match="Cannot read secret file"):
        get_secret("EXAMPLE_SECRET")
