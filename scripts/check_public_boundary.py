"""Validate the documentation and synthetic-data boundary of the public toolkit."""

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_API_NAMES = {
    "CONSUMER_SOURCES",
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "DISCOGS_DATA_TYPES",
    "MUSICBRAINZ_DATA_TYPES",
    "dead_letter_exchange_name",
    "dead_letter_queue_name",
    "entity_types",
    "exchange_name",
    "exchange_prefix",
    "get_secret",
    "queue_name",
}
PROHIBITED_PUBLIC_PATTERNS = {
    "absolute workstation path": re.compile(r"(?:/Users/|/home/)[A-Za-z0-9._-]+/"),
    "customer record identifier": re.compile(r"(?i)\bcustomer[_ -]?id\s*[:=]\s*[A-Za-z0-9-]+"),
    "incident evidence identifier": re.compile(r"(?i)\b(?:INC|SEV|CASE)-\d{3,}\b"),
    "internal hostname": re.compile(r"(?i)https?://[^\s)>]*(?:\.internal|\.corp|\.lan|\.local)(?::\d+)?"),
    "private IPv4 address": re.compile(r"https?://(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)"),
    "private procedure path": re.compile(r"(?i)\brunbooks?/"),
    "repository planning path": re.compile(r"(?:\.planning/|docs/superpowers/|wt/bead/)"),
    "real credential assignment": re.compile(
        r"(?m)^\s*(?:export\s+)?[A-Z0-9_]*(?:PASSWORD|TOKEN|SECRET|API_KEY)[A-Z0-9_]*\s*=\s*"
        r"(?!/run/secrets/example-|\$\{|<)[^\s#]+"
    ),
}


def public_files(root: Path) -> list[Path]:
    """Return artifacts intended to explain or configure the public toolkit."""
    return [
        root / "README.md",
        root / "utilities/README.md",
        *sorted((root / "docs").glob("*.md")),
        *sorted((root / "examples").glob("*")),
    ]


def find_prohibited_material(files: list[Path]) -> list[str]:
    """Return public-file findings for common private or real-data patterns."""
    findings: list[str] = []
    for path in files:
        text = path.read_text()
        for description, pattern in PROHIBITED_PUBLIC_PATTERNS.items():
            if pattern.search(text):
                try:
                    display_path = path.relative_to(ROOT)
                except ValueError:
                    display_path = path
                findings.append(f"{display_path}: {description}")
    return findings


def validate_synthetic_environment(path: Path) -> None:
    """Require reserved, non-secret values in the tracked environment example."""
    values = dict(line.split("=", 1) for line in path.read_text().splitlines() if line and not line.startswith("#"))
    assert values["RABBITMQ_URL"] == "https://rabbitmq.example.test"
    assert values["RABBITMQ_USERNAME"] == "observer"
    assert values["NEO4J_USERNAME"] == "observer"
    assert values["POSTGRES_USERNAME"] == "observer"
    assert values["POSTGRES_DATABASE"] == "groovemap_example"
    assert values["RABBITMQ_PASSWORD_FILE"].startswith("/run/secrets/example-")
    assert values["NEO4J_PASSWORD_FILE"].startswith("/run/secrets/example-")
    assert "RABBITMQ_PASSWORD" not in values
    assert "NEO4J_PASSWORD" not in values


def validate_repository(root: Path = ROOT) -> None:
    """Validate command/API documentation, branding, diagrams, and public data."""
    root_readme = (root / "README.md").read_text()
    command_reference = (root / "utilities/README.md").read_text()
    api_reference = (root / "docs/python-api.md").read_text()
    docs_index = (root / "docs/README.md").read_text()
    architecture = (root / "docs/architecture.md").read_text()

    with (root / "pyproject.toml").open("rb") as source:
        commands = set(tomllib.load(source)["project"]["scripts"])
    for command in commands:
        assert f"`{command}`" in root_readme
        assert f"`{command}" in command_reference
    for api_name in PUBLIC_API_NAMES:
        assert f"`{api_name}`" in api_reference or f"`{api_name}(" in api_reference

    for document in ("architecture.md", "configuration.md", "python-api.md", "security.md", "extraction.md"):
        assert f"({document})" in docs_index
    assert "```mermaid" in architecture
    assert not re.search(r"```(?:plantuml|dot|graphviz|ascii)\b", "\n".join(path.read_text() for path in public_files(root)))

    active_text = "\n".join(
        path.read_text() for extension in ("*.json", "*.md", "*.py", "*.toml") for path in root.rglob(extension) if ".venv" not in path.parts
    )
    assert "discogs" + "ography" not in active_text.lower()
    assert "claude" + ".md" not in active_text.lower()
    assert "GrooveMap" in root_readme
    assert "operations-toolkit" in root_readme

    findings = find_prohibited_material(public_files(root))
    assert not findings, "\n".join(findings)
    validate_synthetic_environment(root / "examples/toolkit.env.example")


if __name__ == "__main__":
    validate_repository()
