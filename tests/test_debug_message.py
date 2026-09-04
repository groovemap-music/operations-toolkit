"""Tests for utilities/debug_message.py — the queue message peeker/analyzer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from utilities import debug_message


def _fake_connection(body: bytes | None) -> MagicMock:
    """Build a pika BlockingConnection mock; ``body=None`` means empty queue."""
    connection = MagicMock()
    connection.is_closed = False
    channel = MagicMock()
    connection.channel.return_value = channel
    if body is None:
        channel.basic_get.return_value = (None, None, None)
    else:
        method = MagicMock()
        method.delivery_tag = 42
        channel.basic_get.return_value = (method, MagicMock(), body)
    return connection


# --------------------------------------------------------------------------- #
# get_message_from_queue
# --------------------------------------------------------------------------- #
def test_get_message_returns_and_requeues() -> None:
    conn = _fake_connection(json.dumps({"id": "1", "title": "x"}).encode())
    with patch.object(debug_message.pika, "BlockingConnection", return_value=conn):
        msg = debug_message.get_message_from_queue("q", username="u", password="p")  # noqa: S106

    assert msg == {"id": "1", "title": "x"}
    channel = conn.channel.return_value
    channel.basic_nack.assert_called_once_with(delivery_tag=42, requeue=True)
    conn.close.assert_called_once()


def test_get_message_empty_queue() -> None:
    conn = _fake_connection(None)
    with patch.object(debug_message.pika, "BlockingConnection", return_value=conn):
        assert debug_message.get_message_from_queue("q") is None
    conn.close.assert_called_once()


def test_get_message_handles_exception(capsys) -> None:
    with patch.object(debug_message.pika, "BlockingConnection", side_effect=RuntimeError("nope")):
        assert debug_message.get_message_from_queue("q") is None
    assert "Error: nope" in capsys.readouterr().out


def test_get_message_skips_close_when_already_closed() -> None:
    conn = _fake_connection(json.dumps({"id": "1"}).encode())
    conn.is_closed = True
    with patch.object(debug_message.pika, "BlockingConnection", return_value=conn):
        debug_message.get_message_from_queue("q")
    conn.close.assert_not_called()


# --------------------------------------------------------------------------- #
# analyze_message
# --------------------------------------------------------------------------- #
def test_analyze_message_none(capsys) -> None:
    debug_message.analyze_message(None, "masters", "discogs")
    assert "No message available in queue" in capsys.readouterr().out


def test_analyze_masters_complete(capsys) -> None:
    message = {
        "id": "123",
        "title": "A Record",
        "sha256": "abcdef0123456789abcdef",
        "genres": ["rock"],
        "artists": {"name": "artist"},
        "year": 1999,
    }
    debug_message.analyze_message(message, "masters", "discogs")
    out = capsys.readouterr().out
    assert "Message ID: 123" in out
    assert "✓ title" in out
    assert "✓ genres" in out  # list optional field
    assert "✓ artists" in out  # dict optional field
    assert "- members: not present" not in out  # members not an optional for masters
    assert "No obvious issues detected" in out


def test_analyze_masters_missing_required(capsys) -> None:
    debug_message.analyze_message({"title": "no id here"}, "masters", "discogs")
    out = capsys.readouterr().out
    assert "✗ id: MISSING" in out
    assert "Missing required fields: id, sha256" in out


def test_analyze_masters_nested_artist_issues(capsys) -> None:
    message = {
        "id": "1",
        "title": "t",
        "sha256": "s",
        "artists": {"artist": [{"id": "a"}, {"name": "no-id"}]},
    }
    debug_message.analyze_message(message, "masters", "discogs")
    assert "Artist 1 missing 'id' field" in capsys.readouterr().out


def test_analyze_masters_single_artist_missing_id(capsys) -> None:
    message = {"id": "1", "title": "t", "sha256": "s", "artists": {"artist": {"name": "solo"}}}
    debug_message.analyze_message(message, "masters", "discogs")
    assert "Single artist missing 'id' field" in capsys.readouterr().out


@pytest.mark.parametrize("mtype", ["artists", "labels", "releases", "unknown"])
def test_analyze_other_types(mtype: str, capsys) -> None:
    message = {"id": "1", "name": "n", "title": "t", "sha256": "s"}
    debug_message.analyze_message(message, mtype, "discogs")
    assert "Message Analysis" in capsys.readouterr().out


def test_analyze_truncates_large_message(capsys) -> None:
    message = {"id": "1", "sha256": "s", "blob": "x" * 5000}
    debug_message.analyze_message(message, "unknown", "discogs")
    assert "..." in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# analyze_message — MusicBrainz schema regression
# --------------------------------------------------------------------------- #
def test_analyze_musicbrainz_release_uses_name_not_title(capsys) -> None:
    """A real, well-formed MusicBrainz release message (per
    extractor/src/jsonl_parser.rs::parse_mb_release_line: "name", empty-string
    "sha256", no "title") must NOT be flagged as missing "title" — that was the
    exact false positive this bead reports."""
    message = {
        "id": "mbid-1234",
        "name": "Abbey Road",
        "sha256": "",
        "disambiguation": "",
        "barcode": "0602567900828",
        "status": "Official",
    }
    debug_message.analyze_message(message, "releases", "musicbrainz")
    out = capsys.readouterr().out
    assert "✗ title: MISSING" not in out
    assert "Missing required fields" not in out
    assert "✓ name" in out


def test_analyze_musicbrainz_release_group_uses_name(capsys) -> None:
    message = {"id": "mbid-rg-1", "name": "Abbey Road", "sha256": "", "mb_type": "Album"}
    debug_message.analyze_message(message, "release-groups", "musicbrainz")
    out = capsys.readouterr().out
    assert "Missing required fields" not in out


def test_analyze_discogs_release_still_requires_title(capsys) -> None:
    """The Discogs schema must still require 'title' — this fix must not weaken
    validation for the source it was already correct for."""
    message = {"id": "1", "sha256": "s"}
    debug_message.analyze_message(message, "releases", "discogs")
    out = capsys.readouterr().out
    assert "✗ title: MISSING" in out
    assert "Missing required fields: title" in out


# --------------------------------------------------------------------------- #
# analyze_message — media block (ADR 0007)
# --------------------------------------------------------------------------- #
_WELL_FORMED_MEDIA = {
    "taxonomy_version": "1",
    "items": [
        {
            "family": "vinyl",
            "medium": "vinyl_12",
            "qty": 1,
            "size_inches": 12,
            "speed_rpm": None,
            "channels": None,
            "codec": None,
            "variants": [],
            "appearance": [],
            "position": None,
            "track_count": None,
            "source": {"provider": "discogs", "name": "Vinyl", "descriptions": ["LP", "Album"], "text": None},
        }
    ],
    "families": ["vinyl"],
    "release_kind": "album",
    "traits": [],
    "edition": [],
    "packaging": None,
    "container": None,
    "flags": [],
    "unmapped": {"formats": [], "descriptions": []},
}


def test_analyze_discogs_release_media_absent(capsys) -> None:
    message = {"id": "1", "title": "t", "sha256": "s"}
    debug_message.analyze_message(message, "releases", "discogs")
    out = capsys.readouterr().out
    assert "- media: not present" in out
    assert "No obvious issues detected" in out


def test_analyze_discogs_release_media_present_well_formed(capsys) -> None:
    message = {"id": "1", "title": "t", "sha256": "s", "media": _WELL_FORMED_MEDIA}
    debug_message.analyze_message(message, "releases", "discogs")
    out = capsys.readouterr().out
    assert "✓ media: dict" in out
    assert "No obvious issues detected" in out


def test_analyze_discogs_release_media_malformed_not_object(capsys) -> None:
    message = {"id": "1", "title": "t", "sha256": "s", "media": "not-an-object"}
    debug_message.analyze_message(message, "releases", "discogs")
    out = capsys.readouterr().out
    assert "media: expected object, got str" in out


def test_analyze_discogs_release_media_malformed_missing_lists(capsys) -> None:
    message = {"id": "1", "title": "t", "sha256": "s", "media": {"taxonomy_version": "1"}}
    debug_message.analyze_message(message, "releases", "discogs")
    out = capsys.readouterr().out
    assert "media.families: expected list" in out
    assert "media.items: expected list" in out
    assert "media.unmapped: expected object" in out


def test_analyze_musicbrainz_release_media_absent(capsys) -> None:
    message = {"id": "mbid-1", "name": "n", "sha256": ""}
    debug_message.analyze_message(message, "releases", "musicbrainz")
    out = capsys.readouterr().out
    assert "- media: not present" in out
    assert "- media_raw: not present" in out
    assert "No obvious issues detected" in out


def test_analyze_musicbrainz_release_media_present_well_formed(capsys) -> None:
    mb_media = dict(_WELL_FORMED_MEDIA)
    mb_media["release_kind"] = None
    mb_media["items"] = [
        {
            **_WELL_FORMED_MEDIA["items"][0],
            "position": 1,
            "track_count": 9,
            "source": {"provider": "musicbrainz", "name": '12" Vinyl', "descriptions": [], "text": None},
        }
    ]
    message = {
        "id": "mbid-1",
        "name": "n",
        "sha256": "",
        "media": mb_media,
        "media_raw": [{"format": '12" Vinyl', "format_id": None, "position": 1, "title": "", "track_count": 9}],
    }
    debug_message.analyze_message(message, "releases", "musicbrainz")
    out = capsys.readouterr().out
    assert "✓ media: dict" in out
    assert "✓ media_raw: list" in out
    assert "No obvious issues detected" in out


def test_analyze_discogs_release_media_malformed_taxonomy_version(capsys) -> None:
    media = dict(_WELL_FORMED_MEDIA)
    media["taxonomy_version"] = 1  # must be a string per ADR 0007
    message = {"id": "1", "title": "t", "sha256": "s", "media": media}
    debug_message.analyze_message(message, "releases", "discogs")
    out = capsys.readouterr().out
    assert "media.taxonomy_version: expected string" in out


def test_analyze_discogs_release_media_malformed_unmapped_descriptions(capsys) -> None:
    media = dict(_WELL_FORMED_MEDIA)
    media["unmapped"] = {"formats": [], "descriptions": "oops"}
    message = {"id": "1", "title": "t", "sha256": "s", "media": media}
    debug_message.analyze_message(message, "releases", "discogs")
    out = capsys.readouterr().out
    assert "media.unmapped.descriptions: expected list" in out


def test_analyze_musicbrainz_release_media_malformed_unmapped_lists(capsys) -> None:
    message = {
        "id": "mbid-1",
        "name": "n",
        "sha256": "",
        "media": {
            "taxonomy_version": "1",
            "items": [],
            "families": [],
            "unmapped": {"formats": "oops", "descriptions": []},
        },
    }
    debug_message.analyze_message(message, "releases", "musicbrainz")
    out = capsys.readouterr().out
    assert "media.unmapped.formats: expected list" in out


def test_analyze_musicbrainz_release_media_raw_malformed(capsys) -> None:
    message = {"id": "mbid-1", "name": "n", "sha256": "", "media_raw": "oops"}
    debug_message.analyze_message(message, "releases", "musicbrainz")
    out = capsys.readouterr().out
    assert "media_raw: expected list, got str" in out


def test_analyze_musicbrainz_release_media_raw_entry_malformed(capsys) -> None:
    message = {"id": "mbid-1", "name": "n", "sha256": "", "media_raw": [{"format": "CD"}, "not-an-object"]}
    debug_message.analyze_message(message, "releases", "musicbrainz")
    out = capsys.readouterr().out
    assert "media_raw[1]: expected object, got str" in out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def test_main_no_args_exits(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(debug_message.sys, "argv", ["debug_message.py"])
    with pytest.raises(SystemExit) as exc:
        debug_message.main()
    assert exc.value.code == 1
    assert "Usage:" in capsys.readouterr().out


def test_main_invalid_queue_type(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(debug_message.sys, "argv", ["debug_message.py", "bogus"])
    with pytest.raises(SystemExit) as exc:
        debug_message.main()
    assert exc.value.code == 1
    assert "Invalid queue type" in capsys.readouterr().out


def test_main_invalid_consumer(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(debug_message.sys, "argv", ["debug_message.py", "artists", "bogus"])
    with pytest.raises(SystemExit) as exc:
        debug_message.main()
    assert exc.value.code == 1
    assert "Invalid consumer" in capsys.readouterr().out


def test_main_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(debug_message.sys, "argv", ["debug_message.py", "artists", "tableinator"])
    with (
        patch.object(debug_message, "get_message_from_queue", return_value={"id": "1"}) as getter,
        patch.object(debug_message, "analyze_message") as analyzer,
    ):
        debug_message.main()

    getter.assert_called_once()
    # Queue name is composed from the tableinator prefix + type.
    assert getter.call_args.args[0].endswith("-artists")
    analyzer.assert_called_once_with({"id": "1"}, "artists", "discogs")


def test_main_musicbrainz_consumer_passes_musicbrainz_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(debug_message.sys, "argv", ["debug_message.py", "release-groups", "brainzgraphinator"])
    with (
        patch.object(debug_message, "get_message_from_queue", return_value={"id": "1"}) as getter,
        patch.object(debug_message, "analyze_message") as analyzer,
    ):
        debug_message.main()

    getter.assert_called_once()
    assert getter.call_args.args[0].endswith("-release-groups")
    analyzer.assert_called_once_with({"id": "1"}, "release-groups", "musicbrainz")


# --------------------------------------------------------------------------- #
# main — cross-source (consumer, queue_type) rejection
# --------------------------------------------------------------------------- #
def test_main_rejects_discogs_only_type_for_brainz_consumer(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """ "masters" only exists on the Discogs side — no MusicBrainz consumer ever
    declares a masters queue, so this combination must be rejected up front
    instead of building a queue name that doesn't exist."""
    monkeypatch.setattr(debug_message.sys, "argv", ["debug_message.py", "masters", "brainzgraphinator"])
    with pytest.raises(SystemExit) as exc:
        debug_message.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Invalid queue type" in out
    assert "brainzgraphinator" in out


def test_main_rejects_musicbrainz_only_type_for_discogs_consumer(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """ "release-groups" only exists on the MusicBrainz side — graphinator/
    tableinator never declare a release-groups queue."""
    monkeypatch.setattr(debug_message.sys, "argv", ["debug_message.py", "release-groups", "graphinator"])
    with pytest.raises(SystemExit) as exc:
        debug_message.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Invalid queue type" in out
    assert "graphinator" in out
