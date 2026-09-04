# Operations toolkit command reference

These six commands are the supported CLI surface of the GrooveMap `operations-toolkit`.
They are observational, but their output can reflect live deployment or catalog data. Run
them with least-privileged access and keep captured output out of public artifacts.

## `groovemap-check-errors [minutes]`

Reads recent Docker Compose logs for the six catalog pipeline compatibility service IDs and
groups lines matching error, exception, traceback, and processing-failure patterns.

- `minutes` is optional and defaults to `60`.
- Requires the Docker CLI and access to the target Compose project.
- Returns a summary count; it does not alter containers or logs.
- A Docker timeout or command failure is reported as an observation for that service.

```bash
uv run groovemap-check-errors 30
```

## `groovemap-check-queues`

Performs one read against the RabbitMQ Management API and prints state, ready and
unacknowledged counts, consumers, and available publish/acknowledgement rates for catalog
consumer queues.

- Uses the RabbitMQ URL and credentials described in [configuration](../docs/configuration.md).
- Does not declare, bind, purge, acknowledge, or delete queues.
- Reports connection and HTTP failures without printing credentials.

```bash
uv run groovemap-check-queues
```

## `groovemap-monitor-queues [seconds]`

Repeatedly reads RabbitMQ queue statistics, clears the terminal, and displays ready,
unacknowledged, and total counts. Queues with unacknowledged messages are highlighted.

- `seconds` is optional and defaults to `5`.
- Stop with Ctrl+C.
- An empty successful response is displayed distinctly from a connection failure.

```bash
uv run groovemap-monitor-queues 10
```

## `groovemap-debug-message <entity> [consumer]`

Peeks at one supported catalog-event queue using `basic_get`, immediately requeues the
delivery with `basic_nack`, and then reports required/optional field shape.

- Discogs entities: `artists`, `labels`, `masters`, `releases`.
- MusicBrainz entities: `artists`, `labels`, `release-groups`, `releases`.
- Consumers are the compatibility identifiers the local queue-name adapter composes from both
  promoted catalog-event producer contracts; the default is `graphinator`.
- The command prints message fields and up to 1,000 characters of the message. Treat output as
  operational data.
- A peek can affect delivery ordering even though the message is requeued; do not use it when
  that temporary delivery is unacceptable.

```bash
uv run groovemap-debug-message releases graphinator
```

### Media block on `releases` messages

Both producers attach the additive canonical `media` object to `releases` events (ADR 0007:
canonical media taxonomy). The command lists `media` as an optional field for both Discogs and
MusicBrainz `releases`, and MusicBrainz `releases` also carry `media_raw`, the producer's raw
`{format, format_id, position, title, track_count}` medium list. When `media` or `media_raw` is
present, the command checks its shape — an object with `families`, `items`, and
`taxonomy_version`, and an `unmapped` object with `formats`/`descriptions` — and reports a
specific issue (for example `media.families: expected list`) instead of silently printing a
malformed block as an opaque dict. Absent `media`/`media_raw` is reported as `not present`, not
as an error: the field is optional.

Example release payloads carrying `media` (Discogs) and `media`/`media_raw` (MusicBrainz) are in
[`examples/discogs-release-with-media.json`](../examples/discogs-release-with-media.json) and
[`examples/musicbrainz-release-with-media.json`](../examples/musicbrainz-release-with-media.json).

## `groovemap-healthcheck <process-name>`

Scans the local process table for a command-line argument containing the requested name. The
healthcheck process and all of its ancestors are excluded so it cannot match itself.

- Exits `0` when a matching process exists and `1` otherwise.
- Reads process metadata only; it does not signal or restart processes.

```bash
uv run groovemap-healthcheck catalog-api
```

## `groovemap-system-monitor`

Runs a combined snapshot of Docker Compose containers, RabbitMQ catalog queues, Neo4j node
counts, PostgreSQL table statistics, and recent service error lines.

- Requires Docker plus the deployment-provided database command-line clients in their
  containers.
- Database queries are read-only statistics queries.
- Missing or inaccessible subsystems are reported without stopping the remaining checks.
- Output can reveal topology, object counts, and log excerpts and must be handled accordingly.

```bash
uv run groovemap-system-monitor
```

## Convenience recipes

The same commands are exposed through `just check-errors`, `just check-queues`,
`just monitor-queues`, `just debug-message`, `just healthcheck`, and `just system-monitor`.

See the [public Python API](../docs/python-api.md), [configuration reference](../docs/configuration.md),
and [security boundary](../docs/security.md) for the reusable and operational contracts.
