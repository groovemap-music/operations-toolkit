# Operations toolkit command reference

> 🔧 Read-only debugging and monitoring tools for GrooveMap operations

These packaged commands inspect a GrooveMap deployment without mutating queues or databases.

## 🛠️ Available Tools

### check_errors.py

Scans recent `docker compose logs` output for the pipeline services for error patterns.

```bash
# Check the last 60 minutes (default) across all pipeline services
uv run groovemap-check-errors

# Check a custom time window (minutes)
uv run groovemap-check-errors 30

# Or use just
just check-errors
```

**Features:**

- Checks `extractor-discogs`, `extractor-musicbrainz`, `graphinator`, `tableinator`, `brainzgraphinator`, and `brainztableinator` via `docker compose logs --since=<N>m`
- Matches lines against error patterns (`ERROR`, `Exception`, `Traceback`, `Failed to process...`)
- Groups and counts similar errors per service, printing `✅ No errors found` when clean

### check_queues.py

Displays current RabbitMQ queue statistics.

```bash
uv run groovemap-check-queues
```

**Shows:**

- Queue names and message counts
- Consumer counts per queue
- Message rates (if available)
- Connection status

### monitor_queues.py

Real-time monitoring of RabbitMQ queue activity.

```bash
# Monitor with auto-refresh (default: every 5 seconds)
uv run groovemap-monitor-queues

# Custom refresh interval (seconds)
uv run groovemap-monitor-queues 10

# Or use just
just monitor
```

**Features:**

- Live updates every 5 seconds by default (configurable via a positional interval argument)
- Highlights queues with unacknowledged messages in yellow
- Running total of messages across all `discogsography`/`musicbrainz` queues

### system_monitor.py

Comprehensive system health dashboard.

```bash
# Run system monitor
uv run groovemap-system-monitor

# Or use just
just system-monitor
```

**Displays:**

- Docker container status and health (`docker compose ps`)
- RabbitMQ queue message counts (ready/unacked/total)
- Neo4j node counts by label (via `cypher-shell`)
- PostgreSQL table sizes and row counts (via `psql`)
- Recent `ERROR`/`Failed` log lines for the pipeline services (extractor-discogs, extractor-musicbrainz, graphinator, tableinator, brainzgraphinator, brainztableinator)

### debug_message.py

Peeks at (non-destructively, via `basic_get` + `basic_nack` requeue) a single message from a consumer queue and analyzes its structure — checks required/optional fields for the given data type and flags common issues (missing fields, malformed nested artist entries).

```bash
uv run groovemap-debug-message <queue_type> [consumer]
```

**Arguments:**

- `queue_type`: `artists`, `labels`, `masters`, `releases`, or `release-groups` (MusicBrainz)
- `consumer`: `graphinator`, `tableinator`, `brainzgraphinator`, or `brainztableinator` (default: `graphinator`)

### healthcheck.py

Checks whether a process matching the given name is currently running (via `psutil.process_iter`), matching against each process's command line. Exits `0` if found, `1` otherwise.

```bash
uv run groovemap-healthcheck <process_name>
```

## 🔒 Security Notes

These utilities include narrowly scoped security suppressions for fixed executable names:

- `# nosec B404 B603 B607` / `# noqa: S603 S607` - For `docker compose`/`docker exec` subprocess commands

These suppressions are appropriate because:

- subprocess executable names are fixed;
- every subprocess call has a timeout;
- credentials use environment variables or `<NAME>_FILE` and are never printed;
- operators should supply least-privileged read-only credentials.

## 💡 Usage Tips

1. **Start with system_monitor.py** for overall health
1. **Use check_errors.py** when services report issues
1. **Run monitor_queues.py** to watch message flow
1. **Use debug_message.py** to inspect a queue's message structure

## 🔗 Related Documentation

- [Repository README](../README.md) - setup, security boundary, and release policy
- [Extraction record](../docs/extraction.md) - retained history and source paths
