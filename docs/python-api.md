# Public Python API

The supported reusable API is intentionally smaller than the CLI implementation surface.

## Catalog-event naming

`utilities.catalog_contract` is generated from the promoted producer contract. Supported
functions are:

- `entity_types(source)` — return valid entities for `discogs` or `musicbrainz`.
- `exchange_prefix(source)` — return the configured exchange namespace.
- `exchange_name(source, entity)` — construct a producer exchange name.
- `queue_name(consumer, entity)` — construct a registered consumer queue name.
- `dead_letter_exchange_name(consumer, entity)` — construct the queue's dead-letter exchange.
- `dead_letter_queue_name(consumer, entity)` — construct the queue's dead-letter queue.

The module also exposes `CONTRACT_NAME`, `CONTRACT_VERSION`, `DISCOGS_DATA_TYPES`,
`MUSICBRAINZ_DATA_TYPES`, and `CONSUMER_SOURCES` for discovery. Invalid sources, consumers, or
entity combinations raise `ValueError`. The `AMQP_QUEUE_PREFIX_*` names are compatibility
implementation details and are not part of this supported API.

```python
from utilities.catalog_contract import queue_name

synthetic_queue = queue_name("graphinator", "releases")
```

Do not edit the generated module directly. Promote a reviewed producer contract and run
`just contract-check`.

## Secret lookup

`get_secret(name, default=None)` from `utilities.secrets` checks `<NAME>_FILE` first and reads that file,
then falls back to `<NAME>`, then to the supplied default. It never logs the resolved value. An
unreadable configured file raises `ValueError` naming the variable and path, not its contents.

```python
from utilities.secrets import get_secret

password = get_secret("RABBITMQ_PASSWORD")
```

## Compatibility policy

Functions in command modules remain testable implementation details, not a stable library API.
Automations should invoke the console commands or the two supported modules above. Additions to
the public API require documentation and regression coverage in the same change.
