set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

setup:
    uv sync --dev --frozen

check: format-check lint typecheck coverage contract-check public-boundary-check automation-check build install-check license-check secret-scan bump-preview

# Stateful locally: rewrites formatting in tracked source files; never contacts a deployment.
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

coverage: test

contract-check:
    uv run python scripts/check-contracts.py

public-boundary-check:
    uv run python scripts/check_public_boundary.py

automation-check:
    uv run python scripts/check_automation.py

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

# Create private backup and sanitized mirror evidence only; never change a remote.
history-rehearsal source-repository output-directory:
    PLANNING_ARCHIVE_REPO="${PLANNING_ARCHIVE_REPO}" bash scripts/rehearse-history-sanitization.sh "{{source-repository}}" "{{output-directory}}"

# Observational: reads recent Compose logs and writes only its terminal report.
check-errors *args:
    uv run groovemap-check-errors {{args}}

# Observational: reads one RabbitMQ Management API snapshot without changing queues.
check-queues:
    uv run groovemap-check-queues

# Stateful broker peek: immediately requeues one delivery and may change delivery order.
debug-message *args:
    uv run groovemap-debug-message {{args}}

# Observational: reads the local process table and signals no processes.
healthcheck process:
    uv run groovemap-healthcheck {{process}}

# Observational: repeatedly reads queue statistics until interrupted.
monitor-queues *args:
    uv run groovemap-monitor-queues {{args}}

# Observational: reads deployment health and statistics without applying changes.
system-monitor:
    uv run groovemap-system-monitor
