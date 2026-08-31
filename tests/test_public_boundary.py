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
        "remove .planning/private-notes.md",
        "PASSWORD=not-a-placeholder",
    ],
)
def test_private_operational_material_is_rejected(tmp_path: Path, private_text: str) -> None:
    candidate = tmp_path / "candidate.md"
    candidate.write_text(private_text)

    assert find_prohibited_material([candidate])


def test_current_repository_satisfies_public_boundary() -> None:
    validate_repository()


def test_history_rehearsal_is_backed_up_non_mutating_and_fail_closed() -> None:
    rehearsal = (Path(__file__).resolve().parents[1] / "scripts/rehearse-history-sanitization.sh").read_text()

    for marker in (
        "clone --quiet --mirror --no-local",
        "bundle create",
        "bundle verify",
        "filter-repo --force --invert-paths",
        "--path .planning/",
        "--path docs/superpowers/plans/",
        "--path docs/superpowers/specs/",
        "fsck --full --strict",
        "rev-list --objects --all",
        "gitleaks git",
        "trufflehog git",
        "remote-cutover-approved=false",
        "public-visibility-approved=false",
    ):
        assert marker in rehearsal
    for forbidden in ("git push", "--force-with-lease", "remote set-url"):
        assert forbidden not in rehearsal
