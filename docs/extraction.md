# Source-history provenance

`operations-toolkit` was extracted from the former GrooveMap monolith with relevant utility
and test history preserved. The extraction retained the utility package, its tests, and the
license applicable at the time, then established this independently versioned repository.

The current repository removes monorepo-relative imports and obtains queue vocabulary from
promoted producer contracts. `groovemap.catalog-events/v1` is produced independently by the two
source owners. The promotion records are:

| Source owner | Producer revision | Local provenance | Promoted files |
| --- | --- | --- | --- |
| [`discogs-ingestion`](https://github.com/groovemap-music/discogs-ingestion) | [`c1bf1b4ada3ee88e1e6768a0be7fa6ed1b921831`](https://github.com/groovemap-music/discogs-ingestion/tree/c1bf1b4ada3ee88e1e6768a0be7fa6ed1b921831) | [`discogs/source.json`](../contracts/catalog-events/v1/discogs/source.json) | [`contract.json`](../contracts/catalog-events/v1/discogs/contract.json), [`catalog_contract.py`](../contracts/catalog-events/v1/discogs/python/catalog_contract.py) |
| [`musicbrainz-ingestion`](https://github.com/groovemap-music/musicbrainz-ingestion) | [`f0dae1037c809c6855863aebc35d0a7d21366482`](https://github.com/groovemap-music/musicbrainz-ingestion/tree/f0dae1037c809c6855863aebc35d0a7d21366482) | [`musicbrainz/source.json`](../contracts/catalog-events/v1/musicbrainz/source.json) | [`contract.json`](../contracts/catalog-events/v1/musicbrainz/contract.json), [`catalog_contract.py`](../contracts/catalog-events/v1/musicbrainz/python/catalog_contract.py) |

Each contract and generated Python binding is copied byte-for-byte from its recorded producer
revision. The source record is authoritative for the repository, revision, paths, and SHA-256
digests. `just contract-check` verifies those digests and the producer-specific ownership and
consumer sets. Shared interpretation remains hand-authored in
[`utilities/catalog_contract.py`](../utilities/catalog_contract.py); do not edit a generated
binding to add cross-producer behavior.

No source repository was rewritten or deleted as part of the extraction. Workstation paths,
migration commands, deployment topology, and private operational procedures are intentionally
excluded from this public record.
