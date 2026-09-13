# GrooveMap operations toolkit

`operations-toolkit` packages credential-conscious, primarily observational utilities for
inspecting a GrooveMap deployment. The tools report queue activity, recent service errors,
process presence, container health, and database statistics. `groovemap-debug-message` is the
narrow stateful exception: it gets and immediately requeues one delivery, which can affect
delivery order. The tools do not purge queues, modify databases, restart services, or publish
deployment configuration.

## Supported commands

| Command | Purpose |
| --- | --- |
| `groovemap-check-errors` | Summarize recent error-shaped service log lines. |
| `groovemap-check-queues` | Print a point-in-time RabbitMQ queue snapshot. |
| `groovemap-monitor-queues` | Refresh RabbitMQ queue counts until interrupted. |
| `groovemap-debug-message` | Peek at one catalog message, requeue it, and validate its shape. |
| `groovemap-healthcheck` | Report whether a matching process is present. |
| `groovemap-system-monitor` | Combine container, queue, graph, relational, and log observations. |

The [command reference](utilities/README.md) documents arguments, data access, output, and
failure behavior for every command. The [public Python API](docs/python-api.md) defines the
smaller reusable library surface; other module functions are command implementation details.

## Development

Install the pinned tools and run the credential-free repository gate:

```bash
mise install
just setup
just check
```

Tests use synthetic responses and do not contact a live deployment. The validation and local
maintenance recipes are:

| Recipe | Contract |
| --- | --- |
| `just setup` | Install the frozen development environment. |
| `just format-check` / `just lint` / `just typecheck` | Check formatting, lint, and Python types independently. |
| `just test` / `just coverage` | Run the same unit suite with coverage; `coverage` is the alias used by `check` and CI. |
| `just contract-check` | Verify both promoted producer contracts and generated bindings against their provenance digests. |
| `just public-boundary-check` / `just automation-check` | Check public artifacts and immutable GitHub automation. |
| `just build` / `just install-check` | Build distributions and verify the wheel in an isolated environment. |
| `just license-check` / `just secret-scan` / `just bump-preview` | Check licenses, Git history and worktree secrets, and version consistency. |
| `just check` | Run every credential-free validation capability above. |
| `just audit` | Run the separate, network-backed vulnerability audit. |
| `just format` | Rewrite tracked Python formatting and apply safe Ruff fixes locally. |
| `just bump` | Update local version files, changelog, and lock data without committing, tagging, or publishing. |
| `just release-dry-run` | Run `check`, then build checksums, an SBOM, notices, and exact-source provenance without publishing. |
| `just history-rehearsal SOURCE OUTPUT` | Create private backup and sanitized-history evidence; never change a remote. |

Running bare `just` lists those recipes plus the six explicit operator wrappers documented in
the [command reference](utilities/README.md): `just check-errors`, `just check-queues`,
`just monitor-queues`, `just healthcheck`, and `just system-monitor` are observational;
`just debug-message` performs the documented get-and-requeue operation.

## Safe configuration

Copy [examples/toolkit.env.example](examples/toolkit.env.example) and replace its reserved
example values only in an untracked operator environment. Secret-file variables take
precedence over direct secret variables; never place secret values in shell history,
documentation, fixtures, or commits.

Live commands should run from the deployment's Compose project directory with
least-privileged monitoring accounts. Some output can contain deployment metadata or catalog
message content, so handle command output as operational data and do not attach it to public
issues.

## Repository boundary

This repository owns the six CLIs, the local catalog-event naming adapter, and the
secret-file lookup helper. Deployment topology and operator procedures belong in private
infrastructure repositories. Producer event schemas belong to
[`discogs-ingestion`](https://github.com/groovemap-music/discogs-ingestion) and
[`musicbrainz-ingestion`](https://github.com/groovemap-music/musicbrainz-ingestion); this
repository consumes their separately promoted contracts through the recorded
[Discogs](contracts/catalog-events/v1/discogs/source.json) and
[MusicBrainz](contracts/catalog-events/v1/musicbrainz/source.json) provenance.

See the [documentation index](docs/README.md) for architecture, configuration, security, and
source-history guidance.

## License

The current tree is licensed under the [MIT License](LICENSE). Historical revisions retain
the license terms that applied to them.
