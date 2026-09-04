# GrooveMap operations toolkit

`operations-toolkit` packages credential-conscious, observational utilities for inspecting
a GrooveMap deployment. The tools report queue activity, recent service errors, process
presence, container health, and database statistics. They do not purge queues, modify
databases, restart services, or publish deployment configuration.

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

Useful focused commands are `just test`, `just contract-check`,
`just public-boundary-check`, `just build`, `just audit`, and `just release-dry-run`. Tests use
synthetic responses and do not contact a live deployment. The release dry-run builds checksums,
an SBOM, third-party notices, and exact-source provenance without publishing anything.

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
infrastructure repositories. Producer event schemas belong to `discogs-ingestion` and
`musicbrainz-ingestion`; this repository consumes both promoted contracts in
`contracts/catalog-events/v1/discogs/` and `contracts/catalog-events/v1/musicbrainz/`.

See the [documentation index](docs/README.md) for architecture, configuration, security, and
source-history guidance.

## License

The current tree is licensed under the [MIT License](LICENSE). Historical revisions retain
the license terms that applied to them.
