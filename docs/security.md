# Security and publication boundary

The public repository contains source code, synthetic configuration, the promoted producer
contracts and their generated bindings, and tests. It must remain free of credential values,
live non-public network locations, identifiable customer records, operational event evidence,
and private response procedures.

## Access

- Use monitoring-only RabbitMQ and database accounts.
- Prefer `<NAME>_FILE` variables and narrowly readable files over direct secret variables.
- Run Docker commands only against the intended Compose context.
- Keep default development and validation commands credential-free and offline from live
  infrastructure.

## Output handling

Queue names, counts, container topology, database statistics, logs, and peeked messages can be
sensitive even when the command does not mutate the target. Review output locally, retain it only
as long as necessary, and sanitize any diagnostic shared outside the authorized operator group.
Never attach raw command output to this public repository.

## Repository checks

`just public-boundary-check` verifies that every packaged CLI is documented, the public API is
named, diagrams use Mermaid, configuration examples use reserved synthetic values, and common
private-artifact patterns are absent. `just secret-scan` scans both history and the working tree
with redaction enabled. Both run as part of `just check`.
