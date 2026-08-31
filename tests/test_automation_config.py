"""Regression tests for the repository-owned automation contract."""

from scripts.check_automation import validate_repository


def test_repository_automation_is_complete_and_immutable() -> None:
    validate_repository()
