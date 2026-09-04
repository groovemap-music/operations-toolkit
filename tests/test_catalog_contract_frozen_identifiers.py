"""Frozen-identifier snapshot for the local catalog-events queue-name adapter.

ADR 0005 (https://github.com/groovemap-music/design/blob/main/docs/adr/
0005-source-owned-catalog-ingestion.md) freezes the AMQP identifiers the toolkit
inspects: promoting a producer contract must never rename a durable exchange,
queue, dead-letter exchange, or dead-letter queue that a consumer already holds
messages under. FROZEN_NAMES below is the snapshot captured from
``utilities.catalog_contract`` immediately before the combined catalog-ingestion
binding was replaced by the per-producer promotion, so it records the pre-change
value of every one of those strings.

Do not update these values to match a new promotion -- a diff here means a
durable AMQP identifier moved, and operators would be pointed at a queue that
does not exist. Every assertion checks the adapter, and both promoted contracts'
own ``runtime_identifiers`` blocks, against the snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utilities.catalog_contract import (
    AMQP_QUEUE_PREFIX_BRAINZGRAPHINATOR,
    AMQP_QUEUE_PREFIX_BRAINZTABLEINATOR,
    AMQP_QUEUE_PREFIX_GRAPHINATOR,
    AMQP_QUEUE_PREFIX_TABLEINATOR,
    DATA_TYPES,
    MUSICBRAINZ_DATA_TYPES,
    dead_letter_exchange_name,
    dead_letter_queue_name,
    entity_types,
    exchange_name,
    exchange_prefix,
    queue_name,
)


ROOT = Path(__file__).parent.parent

FROZEN_NAMES: dict[str, dict[str, dict[str, str | dict[str, dict[str, str]]]]] = {
    "discogs": {
        entity: {
            "exchange": f"groovemap-discogs-{entity}",
            "consumers": {
                consumer: {
                    "queue": f"groovemap-discogs-{consumer}-{entity}",
                    "dead_letter_exchange": f"groovemap-discogs-{consumer}-{entity}.dlx",
                    "dead_letter_queue": f"groovemap-discogs-{consumer}-{entity}.dlq",
                }
                for consumer in ("graphinator", "tableinator")
            },
        }
        for entity in ("artists", "labels", "masters", "releases")
    },
    "musicbrainz": {
        entity: {
            "exchange": f"groovemap-musicbrainz-{entity}",
            "consumers": {
                consumer: {
                    "queue": f"groovemap-musicbrainz-{consumer}-{entity}",
                    "dead_letter_exchange": f"groovemap-musicbrainz-{consumer}-{entity}.dlx",
                    "dead_letter_queue": f"groovemap-musicbrainz-{consumer}-{entity}.dlq",
                }
                for consumer in ("brainzgraphinator", "brainztableinator")
            },
        }
        for entity in ("artists", "labels", "release-groups", "releases")
    },
}

# Pre-change values of the compatibility prefixes debug_message builds queue
# names from directly.
FROZEN_QUEUE_PREFIXES = {
    "graphinator": "groovemap-discogs-graphinator",
    "tableinator": "groovemap-discogs-tableinator",
    "brainzgraphinator": "groovemap-musicbrainz-brainzgraphinator",
    "brainztableinator": "groovemap-musicbrainz-brainztableinator",
}


def _consumers(entity_names: dict[str, dict[str, str | dict[str, dict[str, str]]]]) -> dict[str, dict[str, str]]:
    consumers = entity_names["consumers"]
    assert isinstance(consumers, dict)
    return consumers


def test_frozen_names_cover_every_registered_entity_and_consumer() -> None:
    assert set(FROZEN_NAMES["discogs"]) == set(DATA_TYPES)
    assert set(FROZEN_NAMES["musicbrainz"]) == set(MUSICBRAINZ_DATA_TYPES)
    assert {consumer for entity in FROZEN_NAMES["discogs"].values() for consumer in _consumers(entity)} == {
        "graphinator",
        "tableinator",
    }
    assert {consumer for entity in FROZEN_NAMES["musicbrainz"].values() for consumer in _consumers(entity)} == {
        "brainzgraphinator",
        "brainztableinator",
    }


def test_adapter_reproduces_the_frozen_identifiers() -> None:
    for source, entities in FROZEN_NAMES.items():
        for entity, expected in entities.items():
            assert exchange_name(source, entity) == expected["exchange"]
            for consumer, names in _consumers(expected).items():
                assert queue_name(consumer, entity) == names["queue"]
                assert dead_letter_exchange_name(consumer, entity) == names["dead_letter_exchange"]
                assert dead_letter_queue_name(consumer, entity) == names["dead_letter_queue"]


def test_compatibility_queue_prefixes_are_frozen() -> None:
    assert FROZEN_QUEUE_PREFIXES["graphinator"] == AMQP_QUEUE_PREFIX_GRAPHINATOR
    assert FROZEN_QUEUE_PREFIXES["tableinator"] == AMQP_QUEUE_PREFIX_TABLEINATOR
    assert FROZEN_QUEUE_PREFIXES["brainzgraphinator"] == AMQP_QUEUE_PREFIX_BRAINZGRAPHINATOR
    assert FROZEN_QUEUE_PREFIXES["brainztableinator"] == AMQP_QUEUE_PREFIX_BRAINZTABLEINATOR

    for source, entities in FROZEN_NAMES.items():
        for entity, expected in entities.items():
            for consumer, names in _consumers(expected).items():
                assert f"{FROZEN_QUEUE_PREFIXES[consumer]}-{entity}" == names["queue"], source


def test_frozen_identifiers_match_the_promoted_contracts_runtime_identifiers() -> None:
    for source, entities in FROZEN_NAMES.items():
        contract = json.loads((ROOT / "contracts/catalog-events/v1" / source / "contract.json").read_text())
        runtime_identifiers = contract["runtime_identifiers"]

        for entity, expected in entities.items():
            assert runtime_identifiers["exchanges"][entity] == expected["exchange"]
            for consumer, names in _consumers(expected).items():
                queue = runtime_identifiers["queues"][consumer][entity]
                assert queue["name"] == names["queue"]
                assert queue["dead_letter_exchange"] == names["dead_letter_exchange"]
                assert queue["dead_letter_queue"] == names["dead_letter_queue"]


def test_unregistered_sources_consumers_and_entities_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown catalog source"):
        entity_types("bandcamp")
    with pytest.raises(ValueError, match="Unknown catalog source"):
        exchange_prefix("bandcamp")
    with pytest.raises(ValueError, match="Unknown catalog consumer"):
        queue_name("scrobbleinator", "releases")
    with pytest.raises(ValueError, match="Unknown discogs entity"):
        exchange_name("discogs", "release-groups")
    with pytest.raises(ValueError, match="Unknown musicbrainz entity"):
        queue_name("brainzgraphinator", "masters")
