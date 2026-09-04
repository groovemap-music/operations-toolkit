"""Verify the promoted per-producer catalog-event contracts and their bindings."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_EVENTS = ROOT / "contracts/catalog-events/v1"

# groovemap.catalog-events/v1 is produced independently by two source-owned repositories
# (ADR 0005); the toolkit promotes each producer's contract and generated Python binding
# byte-for-byte rather than consuming one combined upstream.
PRODUCER_REPOSITORIES = {
    "discogs": "https://github.com/groovemap-music/discogs-ingestion",
    "musicbrainz": "https://github.com/groovemap-music/musicbrainz-ingestion",
}
CONSUMERS = {
    "discogs": {"graphinator", "tableinator"},
    "musicbrainz": {"brainzgraphinator", "brainztableinator"},
}


def digest(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest for a file."""
    return sha256(path.read_bytes()).hexdigest()


assert not (CATALOG_EVENTS / "source.json").exists(), "the combined catalog-ingestion pin was replaced by per-producer pins"
assert not (CATALOG_EVENTS / "contract.json").exists(), "the combined catalog-ingestion contract was replaced by per-producer contracts"

for producer, repository in PRODUCER_REPOSITORIES.items():
    producer_root = CATALOG_EVENTS / producer
    source = json.loads((producer_root / "source.json").read_text())
    contract_path = ROOT / source["contract_path"]
    binding_path = ROOT / source["binding_path"]

    assert source["producer_repository"] == repository
    assert len(source["producer_commit"]) == 40
    assert contract_path == producer_root / "contract.json"
    assert binding_path == producer_root / "python/catalog_contract.py"
    assert digest(contract_path) == source["contract_sha256"], f"{producer} contract drifted from its recorded digest"
    assert digest(binding_path) == source["binding_sha256"], f"{producer} binding drifted from its recorded digest"

    contract = json.loads(contract_path.read_text())
    assert contract["contract"] == "groovemap.catalog-events"
    assert contract["version"] == 1
    assert set(contract["sources"]) == {producer}
    assert set(contract["consumers"]) == CONSUMERS[producer]
    assert set(contract["runtime_identifiers"]["queues"]) == CONSUMERS[producer]
