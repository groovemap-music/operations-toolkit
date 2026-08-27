# GrooveMap operations toolkit

Focused operator CLIs for inspecting GrooveMap queues, service errors, process health,
containers, Neo4j, and PostgreSQL. The tools are observational by default: they do not
purge queues, mutate databases, restart services, or print configured secret values.

## Development

Install the pinned tools with `mise install`, then use the stable repository interface:

```bash
just setup
just check
just test
just build
```

`just check` is credential-free. Live operator commands require access to the target
deployment and should be run with the least-privileged RabbitMQ/database accounts that can
read the requested health or statistics surfaces.

## Operator commands

```bash
just check-errors 60
just check-queues
just monitor-queues 5
just system-monitor
just debug-message releases graphinator
just healthcheck graphinator
```

Passwords use the standard `<NAME>_FILE` convention first, then `<NAME>` from the
environment. Do not pass secrets as command-line arguments or commit `.env` files.

The queue naming vocabulary in `utilities/catalog_contract.py` is an exact generated
binding from the producer contract pinned in `contracts/catalog-events/v1/source.json`.
Updates must promote a reviewed producer commit and pass `just contract-check`.

## Release boundary

This repository versions one Python wheel containing all six CLIs. Commitizen reads the
PEP 621 version in `pyproject.toml` and uses annotated `v$version` tags. The dry run
generates checksums, an SBOM, third-party notices, and build metadata. `just bump-preview`
and `just release-dry-run` do not create commits, tags, releases, or published packages.

See [utilities/README.md](utilities/README.md) for command behavior and
[docs/extraction.md](docs/extraction.md) for the history-preserving extraction record.

## License

The current tree is licensed under the PolyForm Noncommercial License 1.0.0. Historical
revisions retain the license text applicable at that time.
