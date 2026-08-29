set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

setup:
    uv sync --dev --frozen

check: format-check lint typecheck test contract-check public-boundary-check build install-check license-check secret-scan bump-preview

format:
    uv run ruff format .
    uv run ruff check --fix .

format-check:
    uv run ruff format --check .

lint:
    uv run ruff check .

typecheck:
    uv run mypy

test:
    uv run pytest --cov=utilities --cov-report=term-missing --cov-report=xml

contract-check:
    uv run python scripts/check-contract.py

public-boundary-check:
    uv run python scripts/check_public_boundary.py

build:
    uv build --out-dir dist --clear

install-check: build
    bash scripts/install-check.sh

license-check:
    uv run python scripts/check-license.py
    uv run pip-licenses --fail-on "GPL-2.0-only;GPL-3.0-only;AGPL-3.0-only"

secret-scan:
    gitleaks git --redact --no-banner
    gitleaks dir . --redact --no-banner

audit:
    uv run pip-audit

bump-preview:
    uv run cz bump --dry-run --changelog --yes --check-consistency

# Update local version metadata and changelog only; do not commit, tag, push, or publish.
bump:
    uv run cz bump --version-files-only --changelog --yes --check-consistency
    uv lock

release-dry-run: check
    bash scripts/release-dry-run.sh

check-errors *args:
    uv run groovemap-check-errors {{args}}

check-queues:
    uv run groovemap-check-queues

debug-message *args:
    uv run groovemap-debug-message {{args}}

healthcheck process:
    uv run groovemap-healthcheck {{process}}

monitor-queues *args:
    uv run groovemap-monitor-queues {{args}}

system-monitor:
    uv run groovemap-system-monitor
