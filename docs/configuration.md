# Configuration

The tools read configuration from the environment. Examples use reserved synthetic domains and
placeholder secret-file paths; this repository does not contain a deployable environment.

| Variable | Used by | Default | Meaning |
| --- | --- | --- | --- |
| `RABBITMQ_URL` | queue checks and monitors | `http://localhost:15672` | RabbitMQ Management API base URL. |
| `RABBITMQ_USERNAME` | RabbitMQ tools | `groovemap` | Least-privileged monitoring account. |
| `RABBITMQ_PASSWORD_FILE` | RabbitMQ tools | unset | File containing the password; preferred. |
| `RABBITMQ_PASSWORD` | RabbitMQ tools | empty | Direct fallback when no file variable is set. |
| `NEO4J_USERNAME` | system monitor | `neo4j` | Neo4j read-only account passed into the container. |
| `NEO4J_PASSWORD_FILE` | system monitor | unset | File containing the Neo4j password; preferred. |
| `NEO4J_PASSWORD` | system monitor | empty | Direct fallback when no file variable is set. |
| `POSTGRES_USERNAME` | system monitor | `groovemap` | PostgreSQL statistics account. |
| `POSTGRES_DATABASE` | system monitor | `groovemap` | Database inspected by the statistics query. |
| `DISCOGS_EXCHANGE_PREFIX` | queue naming | `groovemap-discogs` | Discogs exchange/queue namespace. |
| `MUSICBRAINZ_EXCHANGE_PREFIX` | queue naming | `groovemap-musicbrainz` | MusicBrainz exchange/queue namespace. |

`groovemap-debug-message` connects to RabbitMQ on the local host through its CLI. Library callers
can pass a synthetic or deployment-provided host to `get_message_from_queue`; this repository
does not publish a live broker address.

## Synthetic example

The tracked [example file](../examples/toolkit.env.example) is deliberately non-deployable. To
prepare a private operator environment, copy it outside the repository and replace values there:

```bash
set -a
source /path/to/private/toolkit.env
set +a
uv run groovemap-check-queues
```

Do not commit the copied file or secret-file contents.
