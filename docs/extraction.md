# Source-history provenance

`operations-toolkit` was extracted from the former GrooveMap monolith with relevant utility
and test history preserved. The extraction retained the utility package, its tests, and the
license applicable at the time, then established this independently versioned repository.

The current repository removes monorepo-relative imports and obtains queue vocabulary from
promoted producer contracts. `groovemap.catalog-events/v1` is produced independently by
`discogs-ingestion` and `musicbrainz-ingestion`, so each producer's contract and generated
Python binding is promoted byte-for-byte into `contracts/catalog-events/v1/discogs/` and
`contracts/catalog-events/v1/musicbrainz/`, with the producer revision and content digests
recorded in that subdirectory's `source.json`. `just contract-check` verifies both promotions
against their recorded digests.

No source repository was rewritten or deleted as part of the extraction. Workstation paths,
migration commands, deployment topology, and private operational procedures are intentionally
excluded from this public record.
