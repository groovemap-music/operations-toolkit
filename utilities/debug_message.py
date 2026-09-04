#!/usr/bin/env python3

import json
import os
import sys
from typing import Any

import pika

from utilities.catalog_contract import (
    AMQP_QUEUE_PREFIX_BRAINZGRAPHINATOR,
    AMQP_QUEUE_PREFIX_BRAINZTABLEINATOR,
    AMQP_QUEUE_PREFIX_GRAPHINATOR,
    AMQP_QUEUE_PREFIX_TABLEINATOR,
)
from utilities.secrets import get_secret


def get_message_from_queue(
    queue_name: str,
    host: str = "localhost",
    username: str | None = None,
    password: str | None = None,
) -> dict[str, Any] | None:
    """Peek at a message from the queue without consuming it."""
    username = username or os.environ.get("RABBITMQ_USERNAME", "groovemap")
    password = password or get_secret("RABBITMQ_PASSWORD", "")
    connection = None
    try:
        # Connect to RabbitMQ
        credentials = pika.PlainCredentials(username, password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, credentials=credentials, socket_timeout=10, blocked_connection_timeout=30)
        )
        channel = connection.channel()

        # Get a single message
        method, _properties, body = channel.basic_get(queue=queue_name, auto_ack=False)

        if method:
            # Reject the message to put it back in the queue before parsing
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            # Parse the message (safe to fail now — message is already requeued)
            message: dict[str, Any] = json.loads(body)
            return message
        else:
            return None

    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        if connection and not connection.is_closed:
            connection.close()


# Field specs are keyed on (source, message_type) because the type names
# "artists"/"labels"/"releases" are shared between Discogs and MusicBrainz, but
# the wire schemas differ. Discogs messages carry "title" for masters/releases;
# MusicBrainz messages carry "name" for every type (parse_mb_release_line emits
# "name": v["title"]) and always set "sha256" to the empty string rather than
# omitting it. Keep these distinctions covered as a wire-shape regression.
#
# "media" is the additive canonical media block both producers attach to
# "releases" events (ADR 0007: /design/docs/adr/0007-canonical-media-taxonomy.md,
# shape: /design/taxonomy/media/v1/media-block.schema.json). MusicBrainz also
# carries "media_raw", the raw {format, format_id, position, title, track_count}
# medium list its producer keeps alongside the mapped block.
_DISCOGS_FIELD_SPECS: dict[str, tuple[list[str], list[str]]] = {
    "masters": (["id", "title", "sha256"], ["artists", "genres", "styles", "year"]),
    "artists": (["id", "name", "sha256"], ["members", "groups", "aliases"]),
    "labels": (["id", "name", "sha256"], ["parentLabel", "sublabels"]),
    "releases": (["id", "title", "sha256"], ["artists", "labels", "master_id", "genres", "styles", "media"]),
}

_MUSICBRAINZ_FIELD_SPECS: dict[str, tuple[list[str], list[str]]] = {
    "artists": (["id", "name", "sha256"], ["disambiguation", "external_links"]),
    "labels": (["id", "name", "sha256"], ["disambiguation", "external_links"]),
    "releases": (
        ["id", "name", "sha256"],
        ["disambiguation", "barcode", "status", "release_group_mbid", "external_links", "media", "media_raw"],
    ),
    "release-groups": (["id", "name", "sha256"], ["mb_type", "secondary_types", "first_release_date", "disambiguation", "external_links"]),
}


def _media_shape_issues(media: Any) -> list[str]:
    """Return a description of every way an optional `media` block deviates from
    the ADR 0007 canonical shape.

    This is a lightweight operator-triage check, not full JSON Schema
    validation against media-block.schema.json — it confirms the block is an
    object carrying a `families` list, an `items` list, a string
    `taxonomy_version`, and an `unmapped` object with `formats`/`descriptions`
    lists, so a malformed block is obvious at a glance instead of silently
    printing as "media: dict with N keys"."""
    if not isinstance(media, dict):
        return [f"media: expected object, got {type(media).__name__}"]

    issues: list[str] = []
    if not isinstance(media.get("families"), list):
        issues.append("media.families: expected list")
    if not isinstance(media.get("items"), list):
        issues.append("media.items: expected list")
    if not isinstance(media.get("taxonomy_version"), str):
        issues.append("media.taxonomy_version: expected string")

    unmapped = media.get("unmapped")
    if not isinstance(unmapped, dict):
        issues.append("media.unmapped: expected object")
    else:
        if not isinstance(unmapped.get("formats"), list):
            issues.append("media.unmapped.formats: expected list")
        if not isinstance(unmapped.get("descriptions"), list):
            issues.append("media.unmapped.descriptions: expected list")

    return issues


def _media_raw_shape_issues(media_raw: Any) -> list[str]:
    """Return a description of every way an optional MusicBrainz `media_raw`
    list deviates from its {format, format_id, position, title, track_count}
    per-medium shape (a plain list of objects — the raw pre-taxonomy medium
    entries the MusicBrainz producer keeps alongside the mapped `media` block)."""
    if not isinstance(media_raw, list):
        return [f"media_raw: expected list, got {type(media_raw).__name__}"]
    return [f"media_raw[{i}]: expected object, got {type(entry).__name__}" for i, entry in enumerate(media_raw) if not isinstance(entry, dict)]


def analyze_message(message: dict[str, Any] | None, message_type: str, source: str) -> None:
    """Analyze a message for potential issues.

    ``source`` is "discogs" or "musicbrainz" and selects the correct field
    schema for ``message_type`` — the two sources share type names but not
    wire shapes. The source/entity distinction is part of the promoted contract.
    """
    print(f"\n📋 Message Analysis for {message_type} ({source})")
    print("=" * 60)

    if not message:
        print("No message available in queue")
        return

    # Basic info
    print(f"Message ID: {message.get('id', 'MISSING')}")
    print(f"SHA256: {str(message.get('sha256', 'MISSING'))[:16]}...")

    # Check for required fields based on (source, type)
    field_specs = _MUSICBRAINZ_FIELD_SPECS if source == "musicbrainz" else _DISCOGS_FIELD_SPECS
    required_fields, optional_fields = field_specs.get(message_type, (["id", "sha256"], []))

    print("\n✅ Required Fields:")
    missing_required = []
    for field in required_fields:
        if field in message:
            print(f"  ✓ {field}: {str(message[field])[:50]}...")
        else:
            missing_required.append(field)
            print(f"  ✗ {field}: MISSING")

    print("\n📌 Optional Fields:")
    for field in optional_fields:
        if field in message:
            value = message[field]
            if isinstance(value, dict):
                print(f"  ✓ {field}: {type(value).__name__} with {len(value)} keys")
            elif isinstance(value, list):
                print(f"  ✓ {field}: {type(value).__name__} with {len(value)} items")
            else:
                print(f"  ✓ {field}: {str(value)[:50]}...")
        else:
            print(f"  - {field}: not present")

    # Check for potential issues
    print("\n⚠️  Potential Issues:")
    issues = []

    if missing_required:
        issues.append(f"Missing required fields: {', '.join(missing_required)}")

    # Check for nested structure issues
    if message_type == "masters" and "artists" in message:
        artists = message["artists"]
        if isinstance(artists, dict) and "artist" in artists:
            artist_list = artists["artist"]
            if isinstance(artist_list, list):
                for i, artist in enumerate(artist_list[:3]):  # Check first 3
                    if not isinstance(artist, dict) or "id" not in artist:
                        issues.append(f"Artist {i} missing 'id' field")
            elif isinstance(artist_list, dict) and "id" not in artist_list:
                issues.append("Single artist missing 'id' field")

    if "media" in message:
        issues.extend(_media_shape_issues(message["media"]))

    if "media_raw" in message:
        issues.extend(_media_raw_shape_issues(message["media_raw"]))

    if issues:
        for issue in issues:
            print(f"  • {issue}")
    else:
        print("  No obvious issues detected")

    # Show full message structure
    print("\n📄 Full Message Structure:")
    formatted = json.dumps(message, indent=2)
    print(formatted[:1000] + "..." if len(formatted) > 1000 else formatted)


_CONSUMER_PREFIXES = {
    "graphinator": AMQP_QUEUE_PREFIX_GRAPHINATOR,
    "tableinator": AMQP_QUEUE_PREFIX_TABLEINATOR,
    "brainzgraphinator": AMQP_QUEUE_PREFIX_BRAINZGRAPHINATOR,
    "brainztableinator": AMQP_QUEUE_PREFIX_BRAINZTABLEINATOR,
}

_DISCOGS_TYPES = ["artists", "labels", "masters", "releases"]
_MUSICBRAINZ_TYPES = ["artists", "labels", "release-groups", "releases"]

# Consumers that read from the MusicBrainz fanout exchanges — every other
# consumer (graphinator/tableinator) reads from the Discogs exchanges. Used to
# pick the correct queue-type set AND field schema for a given consumer
# by the promoted producer contract.
_BRAINZ_CONSUMERS = {"brainzgraphinator", "brainztableinator"}


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: debug_message.py <queue_type> [consumer]")
        print(f"Queue types (Discogs): {', '.join(_DISCOGS_TYPES)}")
        print(f"Queue types (MusicBrainz): {', '.join(_MUSICBRAINZ_TYPES)}")
        print(f"Consumers: {', '.join(_CONSUMER_PREFIXES)} (default: graphinator)")
        sys.exit(1)

    queue_type = sys.argv[1]
    consumer = sys.argv[2] if len(sys.argv) > 2 else "graphinator"

    if consumer not in _CONSUMER_PREFIXES:
        print(f"Invalid consumer: {consumer}. Must be one of: {', '.join(_CONSUMER_PREFIXES)}")
        sys.exit(1)

    source = "musicbrainz" if consumer in _BRAINZ_CONSUMERS else "discogs"
    valid_types = _MUSICBRAINZ_TYPES if source == "musicbrainz" else _DISCOGS_TYPES

    # Validate queue_type against the types the CONSUMER actually supports, not
    # the union of both sources — e.g. "masters brainzgraphinator" or
    # "release-groups graphinator" are impossible (source, type) combinations
    # that previously passed validation and built a queue name no consumer ever
    # declares, producing a confusing broker error instead of a clear message.
    if queue_type not in valid_types:
        print(f"Invalid queue type {queue_type!r} for consumer {consumer!r} (source: {source}). Must be one of: {', '.join(valid_types)}")
        sys.exit(1)

    queue_name = f"{_CONSUMER_PREFIXES[consumer]}-{queue_type}"

    print(f"🔍 Debugging Queue: {queue_name}")

    # Get a message from the queue
    message = get_message_from_queue(queue_name)

    # Analyze the message
    analyze_message(message, queue_type, source)


if __name__ == "__main__":
    main()
