# Architecture

The toolkit is a thin observational layer over standard deployment interfaces. Command modules
format observations for humans; the two source-owned producer contracts own queue naming, which
a hand-authored local adapter composes into one import; the secret helper keeps credential
values out of arguments and logs.

```mermaid
flowchart LR
    Operator[Operator] --> CLI[operations-toolkit CLIs]
    Config[Synthetic or private runtime configuration] --> CLI
    DiscogsContract[discogs-ingestion event contract] --> Adapter[Local queue-name adapter]
    MusicBrainzContract[musicbrainz-ingestion event contract] --> Adapter
    Adapter --> CLI
    CLI -->|read logs and status| Docker[Docker Compose]
    CLI -->|read queue statistics or peek/requeue| RabbitMQ[RabbitMQ]
    CLI -->|read aggregate counts| Neo4j[Neo4j]
    CLI -->|read table statistics| Postgres[PostgreSQL]
    CLI --> Output[Terminal observations]
```

## Ownership

This repository owns:

- six console commands and their presentation behavior;
- the local adapter composing both promoted producers' catalog-event queue naming;
- the environment/secret-file lookup helper;
- synthetic examples and credential-free tests.

It does not own deployment manifests, hostnames, account provisioning, response procedures,
customer records, or service-specific mutation commands. Those concerns remain outside the
public toolkit.

## Side-effect boundary

Most operations are HTTP GETs, read-only database queries, process inspection, or Docker status
and log reads. `groovemap-debug-message` is the narrow exception: it obtains one delivery and
immediately negatively acknowledges it with requeue enabled. The queue content is retained, but
delivery ordering can change, so its documentation calls out that effect explicitly.
