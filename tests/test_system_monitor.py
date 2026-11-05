"""Tests for utilities/system_monitor.py — the whole-system status dashboard.

Pins the repository subprocess-timeout contract (every ``subprocess.run`` passes
``timeout=`` and both ``CalledProcessError`` and ``TimeoutExpired`` are caught)
and the split extractor service names used when scanning logs.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import requests

from utilities import system_monitor


if TYPE_CHECKING:
    import pytest


def _completed(stdout: str) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    return result


# --------------------------------------------------------------------------- #
# get_docker_stats
# --------------------------------------------------------------------------- #
def test_get_docker_stats_json_array() -> None:
    payload = '[{"Name": "a"}, {"Name": "b"}]'
    with patch.object(system_monitor.subprocess, "run", return_value=_completed(payload)) as run:
        result = system_monitor.get_docker_stats()
    assert result == [{"Name": "a"}, {"Name": "b"}]
    assert run.call_args.kwargs["timeout"] == 60


def test_get_docker_stats_json_lines() -> None:
    payload = '{"Name": "a"}\n{"Name": "b"}\n'
    with patch.object(system_monitor.subprocess, "run", return_value=_completed(payload)):
        result = system_monitor.get_docker_stats()
    assert result == [{"Name": "a"}, {"Name": "b"}]


def test_get_docker_stats_called_process_error() -> None:
    with patch.object(system_monitor.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["docker"])):
        assert system_monitor.get_docker_stats() == []


def test_get_docker_stats_timeout() -> None:
    with patch.object(system_monitor.subprocess, "run", side_effect=subprocess.TimeoutExpired(["docker"], 60)):
        assert system_monitor.get_docker_stats() == []


# --------------------------------------------------------------------------- #
# get_queue_stats
# --------------------------------------------------------------------------- #
def test_get_queue_stats_success() -> None:
    with patch.object(system_monitor.queue_metrics, "fetch_queue_metrics", return_value=[{"name": "q"}]) as fetch:
        assert system_monitor.get_queue_stats(base_url="http://prom:15692") == [{"name": "q"}]
    fetch.assert_called_once_with("http://prom:15692")


def test_get_queue_stats_error() -> None:
    with patch.object(system_monitor.queue_metrics, "fetch_queue_metrics", side_effect=requests.RequestException()):
        assert system_monitor.get_queue_stats() is None


# --------------------------------------------------------------------------- #
# get_service_logs
# --------------------------------------------------------------------------- #
def test_get_service_logs_success() -> None:
    with patch.object(system_monitor.subprocess, "run", return_value=_completed("log line")) as run:
        assert system_monitor.get_service_logs("graphinator", 5) == "log line"
    assert run.call_args.kwargs["timeout"] == 60
    assert "--tail=5" in run.call_args.args[0]


def test_get_service_logs_error() -> None:
    with patch.object(system_monitor.subprocess, "run", side_effect=subprocess.TimeoutExpired(["docker"], 60)):
        assert system_monitor.get_service_logs("graphinator") == ""


# --------------------------------------------------------------------------- #
# check_neo4j_status / check_postgres_status
# --------------------------------------------------------------------------- #
def test_check_neo4j_status_success() -> None:
    labels = _completed('label\n"Release"\n"Artist"\n')
    counts = _completed('label, count\n"Release", 5\n"Artist", 2\n')
    with patch.object(system_monitor.subprocess, "run", side_effect=[labels, counts]) as run:
        assert system_monitor.check_neo4j_status() == 'label, count\n"Release", 5\n"Artist", 2\n'
    assert run.call_count == 2
    assert all(call.kwargs["timeout"] == 60 for call in run.call_args_list)
    first, second = (call.args[0][-1] for call in run.call_args_list)
    assert first == system_monitor._labels_query()
    assert second == system_monitor.build_node_count_query(["Release", "Artist"])


def test_cypher_shell_runs_in_read_access_mode() -> None:
    with patch.object(system_monitor.subprocess, "run", return_value=_completed("x")) as run:
        system_monitor._cypher_shell("CALL db.labels() YIELD label RETURN label", {})
    argv = run.call_args.args[0]
    assert argv[argv.index("--access-mode") + 1] == "read"
    assert argv.index("--access-mode") < argv.index("--format")


def test_check_neo4j_status_keeps_labels_with_newlines_and_separators() -> None:
    labels = _completed('label\n"new%0Aline"\n"u2028%E2%80%A8x"\n"ctl%01x"\n')
    counts = _completed('label, count\n"new%0Aline", 2\n"u2028%E2%80%A8x", 1\n"ctl%01x", 1\n')
    with patch.object(system_monitor.subprocess, "run", side_effect=[labels, counts]) as run:
        assert system_monitor.check_neo4j_status() == counts.stdout
    query = run.call_args_list[1].args[0][-1]
    assert "MATCH (n:`new\nline`)" in query
    assert "MATCH (n:`u2028\u2028x`)" in query
    assert "MATCH (n:`ctl\x01x`)" in query
    assert "RETURN 'new%0Aline' AS label" in query


def test_check_neo4j_status_no_labels_skips_count_query() -> None:
    with patch.object(system_monitor.subprocess, "run", return_value=_completed("label\n")) as run:
        assert system_monitor.check_neo4j_status() == "label, count\n"
    assert run.call_count == 1


def test_node_count_query_never_scans_all_nodes() -> None:
    query = system_monitor.build_node_count_query(["Release", "Artist"])
    assert "MATCH (n)" not in query
    assert "labels(n)" not in query
    # Each count(n) is alone in its RETURN so Neo4j plans NodeCountFromCountStore.
    assert "CALL () { MATCH (n:`Release`) RETURN count(n) AS count } RETURN 'Release' AS label, count" in query
    assert "CALL () { MATCH (n:`Artist`) RETURN count(n) AS count } RETURN 'Artist' AS label, count" in query
    assert query.count("UNION ALL") == 1
    assert query.endswith("RETURN label, count ORDER BY count DESC LIMIT 10")


def test_node_count_query_quotes_hostile_labels() -> None:
    query = system_monitor.build_node_count_query(["We`ird", "it's"])
    assert "MATCH (n:`We``ird`)" in query
    assert "RETURN 'We`ird' AS label" in query
    assert "RETURN 'it\\'s' AS label" in query


def test_parse_labels_skips_header_and_decodes() -> None:
    assert system_monitor._parse_labels('label\n"Release"\n"We`ird"\n"a%22b"\n"back%5Cslash"\n') == [
        "Release",
        "We`ird",
        'a"b',
        "back\\slash",
    ]
    assert system_monitor._parse_labels("") == []


ODD_LABELS = [
    "new\nline",
    "tab\there",
    "cr\rhere",
    "ctl\x01x",
    "del\x7fx",
    "u0085\x85x",
    "u2028\u2028x",
    "u2029\u2029x",
    'quote"x',
    "back\\slash",
    "pct%x",
    "pct%22literal",
    "We`ird",
    "it's",
    "emoji 🎵",
]


def test_encode_decode_round_trips_every_odd_label() -> None:
    for label in ODD_LABELS:
        encoded = system_monitor._encode_label(label)
        assert "\n" not in encoded and "\r" not in encoded
        assert not any(char < " " or char in "\x7f\x85\u2028\u2029" for char in encoded), label
        assert system_monitor._decode_label(encoded) == label


def test_labels_query_encodes_in_cypher_and_parses_back() -> None:
    query = system_monitor._labels_query()
    assert query.startswith("CALL db.labels() YIELD label RETURN replace(")
    assert query.endswith(" AS label")
    # Cypher-side encoding must match the Python-side encoding that the count query uses.
    simulated = "\n".join(["label", *(f'"{system_monitor._encode_label(label)}"' for label in ODD_LABELS)])
    assert system_monitor._parse_labels(simulated) == ODD_LABELS


def test_postgres_query_uses_relid_not_unquoted_name() -> None:
    with patch.object(system_monitor.subprocess, "run", return_value=_completed("x")) as run:
        system_monitor.check_postgres_status()
    sql = run.call_args.args[0][-1]
    assert "pg_relation_size(relid)" in sql
    assert "||'.'||" not in sql


def test_check_neo4j_status_error_with_stderr() -> None:
    exc = subprocess.CalledProcessError(1, ["docker"], stderr="boom")
    with patch.object(system_monitor.subprocess, "run", side_effect=exc):
        assert system_monitor.check_neo4j_status() == "Error: boom"


def test_check_neo4j_status_error_without_stderr() -> None:
    exc = subprocess.TimeoutExpired(["docker"], 60)
    with patch.object(system_monitor.subprocess, "run", side_effect=exc):
        assert system_monitor.check_neo4j_status().startswith("Error:")


def test_check_postgres_status_success() -> None:
    with patch.object(system_monitor.subprocess, "run", return_value=_completed("relname | size")):
        assert system_monitor.check_postgres_status() == "relname | size"


def test_check_postgres_status_error_with_stderr() -> None:
    exc = subprocess.CalledProcessError(1, ["docker"], stderr="db down")
    with patch.object(system_monitor.subprocess, "run", side_effect=exc):
        assert system_monitor.check_postgres_status() == "Error: db down"


def test_check_postgres_status_error_without_stderr() -> None:
    with patch.object(system_monitor.subprocess, "run", side_effect=subprocess.TimeoutExpired(["docker"], 60)):
        assert system_monitor.check_postgres_status().startswith("Error:")


# --------------------------------------------------------------------------- #
# monitor_system (integration over the mocked collectors)
# --------------------------------------------------------------------------- #
def test_monitor_system_all_healthy(capsys) -> None:
    containers = [{"Name": "groovemap-graphinator", "State": "running", "Health": "healthy"}]
    queues = [{"name": "groovemap-discogs-artists", "messages_ready": 2, "messages_unacknowledged": 1, "messages": 3}]
    with (
        patch.object(system_monitor, "get_docker_stats", return_value=containers),
        patch.object(system_monitor, "get_queue_stats", return_value=queues),
        patch.object(system_monitor, "check_neo4j_status", return_value="neo4j ok"),
        patch.object(system_monitor, "check_postgres_status", return_value="pg ok"),
        patch.object(system_monitor, "get_service_logs", return_value="INFO all good"),
    ):
        system_monitor.monitor_system()

    out = capsys.readouterr().out
    assert "groovemap-graphinator" in out
    assert "Total messages: 3" in out
    assert "neo4j ok" in out
    assert "pg ok" in out
    assert "No recent errors found" in out


def test_monitor_system_honors_overridden_queue_prefixes(capsys) -> None:
    """The queue filter and display shortening must both follow configured prefixes.

    DISCOGS_EXCHANGE_PREFIX / MUSICBRAINZ_EXCHANGE_PREFIX. With the prefixes hardcoded,
    an override made the filter match nothing and the monitor reported an empty broker."""
    queues = [
        {"name": "staging-discogs-graphinator-artists", "messages_ready": 2, "messages_unacknowledged": 1, "messages": 3},
        {"name": "staging-musicbrainz-brainztableinator-releases", "messages_ready": 0, "messages_unacknowledged": 0, "messages": 4},
    ]
    with (
        patch.object(system_monitor, "DISCOGS_EXCHANGE_PREFIX", "staging-discogs"),
        patch.object(system_monitor, "MUSICBRAINZ_EXCHANGE_PREFIX", "staging-musicbrainz"),
        patch.object(system_monitor, "get_docker_stats", return_value=[]),
        patch.object(system_monitor, "get_queue_stats", return_value=queues),
        patch.object(system_monitor, "check_neo4j_status", return_value="neo4j ok"),
        patch.object(system_monitor, "check_postgres_status", return_value="pg ok"),
        patch.object(system_monitor, "get_service_logs", return_value="INFO all good"),
    ):
        system_monitor.monitor_system()

    out = capsys.readouterr().out
    assert "Total messages: 7" in out
    # Labels are shortened using the overridden prefixes, not left fully qualified.
    assert "graphinator-artists" in out
    assert "mb-brainztableinator-releases" in out
    assert "staging-discogs-graphinator-artists" not in out


def test_monitor_system_all_unavailable(capsys) -> None:
    def fake_logs(service: str, _lines: int = 20) -> str:
        return "ERROR something Failed badly" if service == "graphinator" else ""

    with (
        patch.object(system_monitor, "get_docker_stats", return_value=[]),
        patch.object(system_monitor, "get_queue_stats", return_value=None),
        patch.object(system_monitor, "check_neo4j_status", return_value="Error: no neo4j"),
        patch.object(system_monitor, "check_postgres_status", return_value="Error: no pg"),
        patch.object(system_monitor, "get_service_logs", side_effect=fake_logs),
    ):
        system_monitor.monitor_system()

    out = capsys.readouterr().out
    assert "Unable to fetch container status" in out
    assert "Unable to fetch queue data" in out
    assert "Unable to connect to Neo4j" in out
    assert "Unable to connect to PostgreSQL" in out
    assert "graphinator:" in out


def test_monitor_system_empty_queue_list_is_not_a_fetch_failure(capsys) -> None:
    """An empty successful queue response must remain distinct from a fetch failure.

    A successful HTTP 200 with no queues declared yet must not print the same
    "Unable to fetch queue data" message as a genuine RequestException (None).
    """
    with (
        patch.object(system_monitor, "get_docker_stats", return_value=[]),
        patch.object(system_monitor, "get_queue_stats", return_value=[]),
        patch.object(system_monitor, "check_neo4j_status", return_value="Error: no neo4j"),
        patch.object(system_monitor, "check_postgres_status", return_value="Error: no pg"),
        patch.object(system_monitor, "get_service_logs", return_value=""),
    ):
        system_monitor.monitor_system()

    out = capsys.readouterr().out
    assert "Unable to fetch queue data" not in out
    assert "No queues declared yet" in out


def test_monitor_system_scans_split_extractor_services() -> None:
    """Repository contract: the error scan uses both split extractor services."""
    seen: list[str] = []

    def record(service: str, _lines: int = 20) -> str:
        seen.append(service)
        return ""

    with (
        patch.object(system_monitor, "get_docker_stats", return_value=[]),
        patch.object(system_monitor, "get_queue_stats", return_value=None),
        patch.object(system_monitor, "check_neo4j_status", return_value="Error:"),
        patch.object(system_monitor, "check_postgres_status", return_value="Error:"),
        patch.object(system_monitor, "get_service_logs", side_effect=record),
    ):
        system_monitor.monitor_system()

    assert "extractor-discogs" in seen
    assert "extractor-musicbrainz" in seen
    assert "extractor" not in seen


# --------------------------------------------------------------------------- #
# Docker CLI missing
# --------------------------------------------------------------------------- #
def test_monitor_system_reports_missing_docker_and_continues(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("PATH", "")  # no docker binary can be found
    queue_stats = [{"name": "q", "messages": 3, "messages_ready": 3, "messages_unacknowledged": 0}]
    with patch.object(system_monitor, "get_queue_stats", return_value=queue_stats) as get_queues:
        system_monitor.monitor_system()
    get_queues.assert_called_once()
    out = capsys.readouterr().out
    assert out.count("Docker unavailable: Docker CLI not found on PATH") == 4
    assert "Total messages: 3" in out  # the non-Docker check still ran
    assert "Traceback" not in out
    assert out.rstrip().endswith("=" * 80)  # ran to completion
