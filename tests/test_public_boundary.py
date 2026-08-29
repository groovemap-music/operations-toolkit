"""Regression tests for the public toolkit documentation boundary."""

from pathlib import Path

import pytest

from scripts.check_public_boundary import find_prohibited_material, validate_repository


@pytest.mark.parametrize(
    "private_text",
    [
        "source: /Users/example/work/private-config",
        "customer_id=customer-123",
        "evidence from SEV-1234",
        "endpoint: https://queue.ops.internal",
        "endpoint: http://10.20.30.40",
        "see runbooks/database.md",
        "PASSWORD=not-a-placeholder",
    ],
)
def test_private_operational_material_is_rejected(tmp_path: Path, private_text: str) -> None:
    candidate = tmp_path / "candidate.md"
    candidate.write_text(private_text)

    assert find_prohibited_material([candidate])


def test_current_repository_satisfies_public_boundary() -> None:
    validate_repository()
