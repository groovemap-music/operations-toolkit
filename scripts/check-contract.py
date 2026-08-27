"""Verify the promoted catalog-event contract and generated Python binding."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "contracts/catalog-events/v1/source.json"
CONTRACT = ROOT / "contracts/catalog-events/v1/contract.json"
BINDING = ROOT / "utilities/catalog_contract.py"


def digest(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest for a file."""
    return sha256(path.read_bytes()).hexdigest()


source = json.loads(SOURCE.read_text())
contract = json.loads(CONTRACT.read_text())

assert source["producer_repository"] == "https://github.com/groovemap-music/catalog-ingestion"
assert len(source["producer_commit"]) == 40
assert contract["contract"] == "groovemap.catalog-events"
assert contract["version"] == 1
assert digest(CONTRACT) == source["contract_sha256"]
assert digest(BINDING) == source["binding_sha256"]
