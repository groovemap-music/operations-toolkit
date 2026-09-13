# Operations toolkit command reference

These six commands are the supported CLI surface of the GrooveMap `operations-toolkit`.
Five are observational. `groovemap-debug-message` performs the documented get-and-requeue
operation and can affect delivery ordering. Their output can reflect live deployment or catalog
data, so run them with least-privileged access and keep captured output out of public artifacts.

## `groovemap-check-errors [minutes]`

Reads recent Docker Compose logs for the six catalog pipeline compatibility service IDs and
groups lines matching error, exception, traceback, and processing-failure patterns.

- `minutes` is an integer, optional, and defaults to `60`.
- Requires the Docker CLI and access to the target Compose project.
- Reads `extractor-discogs`, `extractor-musicbrainz`, `graphinator`, `tableinator`,
  `brainzgraphinator`, and `brainztableinator` through `docker compose logs` with a 60-second
  subprocess timeout.
- Groups matching lines by error shape and prints a total count; it does not alter containers or
  logs.
- A Docker timeout or command failure is counted and reported as an observation for that service;
  observed errors do not change the command's exit status.

```bash
uv run groovemap-check-errors 30
```

## `groovemap-check-queues`

Performs one 10-second read against the RabbitMQ Management API `/api/queues` endpoint. It prints
state, total, ready and unacknowledged counts, consumers, optional consumer details, and available
publish/acknowledgement rates for queue names containing `graphinator` or `tableinator`.

- Uses the RabbitMQ URL and credentials described in [configuration](../docs/configuration.md).
- Does not declare, bind, purge, acknowledge, or delete queues.
- Reports connection, HTTP, and payload failures without printing credentials. These observations
  do not change the command's exit status.

```bash
uv run groovemap-check-queues
```

## `groovemap-monitor-queues [seconds]`

Repeatedly reads RabbitMQ queue statistics, clears the terminal, and displays ready,
unacknowledged, and total counts. Queues with unacknowledged messages are highlighted.

- `seconds` is an integer passed to the refresh sleep, optional, and defaults to `5`; use a
  positive value.
- Stop with Ctrl+C.
- An empty successful response is displayed distinctly from a connection failure.
- Displays queues whose names contain `groovemap` or `musicbrainz`; it does not declare, bind,
  purge, acknowledge, or delete them.

```bash
uv run groovemap-monitor-queues 10
```

## `groovemap-debug-message <entity> [consumer]`

Peeks at one supported catalog-event queue using `basic_get`, immediately requeues the
delivery with `basic_nack`, and then reports required/optional field shape.

- Discogs entities: `artists`, `labels`, `masters`, `releases`.
- MusicBrainz entities: `artists`, `labels`, `release-groups`, `releases`.
- Discogs consumers are `graphinator` and `tableinator`; MusicBrainz consumers are
  `brainzgraphinator` and `brainztableinator`. The default is `graphinator`, so omitting the
  consumer selects the Discogs entity vocabulary.
- The selected queue is `groovemap-discogs-{consumer}-{entity}` for Discogs or
  `groovemap-musicbrainz-{consumer}-{entity}` for MusicBrainz under default prefixes.
- Invalid/missing entity or consumer arguments exit `1`. Broker, empty-queue, and parsing
  failures are reported as unavailable-message output after any obtained delivery has been
  requeued.
- The command prints message fields and up to 1,000 characters of the message. Treat output as
  operational data.
- A peek can affect delivery ordering even though the message is requeued; do not use it when
  that temporary delivery is unacceptable.

```bash
uv run groovemap-debug-message releases graphinator
```

### Media block on `releases` messages

Both producers attach the additive canonical `media` object to `releases` events under
[ADR 0007](https://github.com/groovemap-music/design/blob/main/docs/adr/0007-canonical-media-taxonomy.md).
The command lists `media` as an optional field for both sources; MusicBrainz `releases` can also
carry `media_raw`, the producer's raw
`{format, format_id, position, title, track_count}` medium list. The lightweight triage check
requires `media` to be an object with list-valued `families` and `items`, a string
`taxonomy_version`, and an `unmapped` object with list-valued `formats` and `descriptions`.
`media_raw` is checked only as a list of objects, not as a full schema validation. A malformed
present value produces a specific issue such as `media.families: expected list`; an absent
optional value is printed as `not present`, not treated as an error.

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
- Reads the active Compose project, the RabbitMQ Management API, fixed database containers
  `groovemap-neo4j` and `groovemap-postgres`, and the same six compatibility service logs as
  `groovemap-check-errors`.
- Database queries are read-only statistics queries.
- Missing or inaccessible subsystems are reported without stopping the remaining checks.
- Output can reveal topology, object counts, and log excerpts and must be handled accordingly.

```bash
uv run groovemap-system-monitor
```

## Convenience recipes

The same commands are exposed through `just check-errors [minutes]`, `just check-queues`,
`just monitor-queues [seconds]`, `just debug-message <entity> [consumer]`,
`just healthcheck <process-name>`, and `just system-monitor`.
The recipes retain the command boundaries above: five are observational, while
`just debug-message` performs the documented get-and-requeue operation and can affect delivery
ordering.

See the [public Python API](../docs/python-api.md), [configuration reference](../docs/configuration.md),
and [security boundary](../docs/security.md) for the reusable and operational contracts.
