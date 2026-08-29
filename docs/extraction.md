# Source-history provenance

`operations-toolkit` was extracted from the former GrooveMap monolith with relevant utility
and test history preserved. The extraction retained the utility package, its tests, and the
license applicable at the time, then established this independently versioned repository.

The current repository removes monorepo-relative imports and obtains queue vocabulary from a
promoted `catalog-ingestion` contract. The generated binding records its producer revision and
content digest under `contracts/catalog-events/v1/`; `just contract-check` verifies that the
checked-in Python binding remains byte-for-byte consistent with that contract.

No source repository was rewritten or deleted as part of the extraction. Workstation paths,
migration commands, deployment topology, and private operational procedures are intentionally
excluded from this public record.
