#!/usr/bin/env python3

import json
import os
import subprocess  # nosec B404
from typing import Any

import requests

from utilities import queue_metrics
from utilities._transport import DockerUnavailableError, docker_compose_output, docker_run
from utilities.catalog_contract import DISCOGS_EXCHANGE_PREFIX, MUSICBRAINZ_EXCHANGE_PREFIX
from utilities.secrets import get_secret


def get_docker_stats() -> list[dict[str, Any]]:
    """Get Docker container statistics; raises DockerUnavailableError when the Docker CLI cannot run."""
    try:
        output = docker_compose_output(subprocess.run, "ps", "--format", "json").strip()
        containers = json.loads(output) if output.startswith("[") else [json.loads(line) for line in output.split("\n") if line]
        return containers
    except subprocess.CalledProcessError, subprocess.TimeoutExpired:
        return []


def get_queue_stats(base_url: str | None = None) -> list[dict[str, Any]] | None:
    """Fetch queue statistics from the RabbitMQ Prometheus endpoint."""
    try:
        return queue_metrics.fetch_queue_metrics(base_url)
    except requests.RequestException:
        return None


def get_service_logs(service: str, lines: int = 20) -> str:
    """Get recent logs from a service; raises DockerUnavailableError when the Docker CLI cannot run."""
    try:
        return docker_compose_output(subprocess.run, "logs", service, f"--tail={lines}")
    except subprocess.CalledProcessError, subprocess.TimeoutExpired:
        return ""


def _cypher_shell(query: str, env: dict[str, str]) -> str:
    """Run one bounded cypher-shell statement in the Neo4j container and return stdout."""
    result = docker_run(
        subprocess.run,
        ["exec", "-e", "NEO4J_USERNAME", "-e", "NEO4J_PASSWORD", "groovemap-neo4j", "cypher-shell", "--format", "plain", query],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
        env=env,
    )
    stdout: str = result.stdout
    return stdout


def _quote_identifier(name: str) -> str:
    """Backtick-quote a Cypher label so any name from the database is safe to embed."""
    return "`" + name.replace("`", "``") + "`"


def _string_literal(value: str) -> str:
    """Render a single-quoted Cypher string literal."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _parse_labels(output: str) -> list[str]:
    """Parse the single-column plain-format ``db.labels()`` result, skipping the header row."""
    labels = []
    for line in output.splitlines()[1:]:
        value = line.strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            labels.append(value[1:-1].replace('\\"', '"').replace("\\\\", "\\"))
    return labels


def build_node_count_query(labels: list[str]) -> str:
    """Build a per-label node count that Neo4j answers from the count store.

    ``MATCH (n) RETURN labels(n)[0], count(n)`` reads every node. A ``count(n)`` that is alone in
    its RETURN is planned as ``NodeCountFromCountStore`` (one database hit per label), so each
    label gets its own ``CALL () { MATCH (n:L) RETURN count(n) }`` branch; the label name is
    projected outside the subquery so it does not demote the plan to a scan.
    """
    branches = [
        f"CALL () {{ MATCH (n:{_quote_identifier(label)}) RETURN count(n) AS count }} RETURN {_string_literal(label)} AS label, count"
        for label in labels
    ]
    return "CALL () { " + " UNION ALL ".join(branches) + " } RETURN label, count ORDER BY count DESC LIMIT 10"


def check_neo4j_status() -> str:
    """Check Neo4j database status with count-store reads, never a full node scan."""
    neo4j_username = os.environ.get("NEO4J_USERNAME", "neo4j")
    neo4j_password = get_secret("NEO4J_PASSWORD", "")
    env = os.environ.copy()
    env["NEO4J_USERNAME"] = neo4j_username
    env["NEO4J_PASSWORD"] = neo4j_password
    try:
        labels = _parse_labels(_cypher_shell("CALL db.labels() YIELD label RETURN label", env))
        if not labels:
            return "label, count\n"
        return _cypher_shell(build_node_count_query(labels), env)
    except DockerUnavailableError as e:
        return f"Error: {e}"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        stderr = getattr(e, "stderr", None)
        return f"Error: {stderr}" if isinstance(stderr, str) and stderr else f"Error: {e}"


def check_postgres_status() -> str:
    """Check PostgreSQL database status."""
    try:
        result = docker_run(
            subprocess.run,
            [
                "exec",
                "groovemap-postgres",
                "psql",
                "-U",
                os.environ.get("POSTGRES_USERNAME", "groovemap"),
                "-d",
                os.environ.get("POSTGRES_DATABASE", "groovemap"),
                "-t",
                "-c",
                "SELECT relname, pg_size_pretty(pg_relation_size(relid)) as size, n_live_tup as rows FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 10;",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        stdout: str = result.stdout
        return stdout
    except DockerUnavailableError as e:
        return f"Error: {e}"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        stderr = getattr(e, "stderr", None)
        return f"Error: {stderr}" if isinstance(stderr, str) and stderr else f"Error: {e}"


def monitor_system() -> None:
    """Monitor the entire system."""
    print("System Monitor for GrooveMap")
    print("=" * 80)

    print("\n📦 Docker Container Status:")
    print("-" * 40)
    docker_problem: str | None = None
    try:
        containers = get_docker_stats()
    except DockerUnavailableError as e:
        docker_problem = str(e)
        containers = []
    if containers:
        for container in containers:
            health = container.get("Health", "N/A")
            status = container.get("State", "unknown")
            name = container.get("Name", "unknown")
            print(f"  {name:<30} Status: {status:<15} Health: {health}")
    elif docker_problem:
        print(f"  Docker unavailable: {docker_problem}")
    else:
        print("  Unable to fetch container status")

    print("\n📬 RabbitMQ Queue Status:")
    print("-" * 40)
    queues = get_queue_stats()
    # get_queue_stats() returns None only on a genuine fetch failure
    # (RequestException); an empty list is a successful 200 response from a broker
    # with no queues declared yet and must not be conflated with a connectivity
    # error. This mirrors the regression guard in monitor_queues.py.
    if queues is None:
        print("  Unable to fetch queue data")
    elif not queues:
        print("  No queues declared yet")
    else:
        total_messages = 0
        for queue in queues:
            # The broker-side queue regex already selects the contract prefixes. Shorten
            # for display using the env-derived prefixes, not hardcoded literals.
            name = queue["name"].replace(f"{DISCOGS_EXCHANGE_PREFIX}-", "").replace(f"{MUSICBRAINZ_EXCHANGE_PREFIX}-", "mb-")
            ready = queue.get("messages_ready", 0)
            unacked = queue.get("messages_unacknowledged", 0)
            total = queue.get("messages", 0)
            total_messages += total
            print(f"  {name:<30} Ready: {ready:<8} Unacked: {unacked:<8} Total: {total}")
        print(f"\n  Total messages: {total_messages}")

    print("\n🔷 Neo4j Database Status:")
    print("-" * 40)
    neo4j_status = check_neo4j_status()
    if not neo4j_status.startswith("Error:"):
        print(neo4j_status)
    elif "Docker CLI" in neo4j_status:
        print("  Docker unavailable: " + neo4j_status.removeprefix("Error: "))
    else:
        print("  Unable to connect to Neo4j")

    print("\n🐘 PostgreSQL Database Status:")
    print("-" * 40)
    postgres_status = check_postgres_status()
    if not postgres_status.startswith("Error:"):
        print(postgres_status)
    elif "Docker CLI" in postgres_status:
        print("  Docker unavailable: " + postgres_status.removeprefix("Error: "))
    else:
        print("  Unable to connect to PostgreSQL")

    print("\n⚠️  Recent Errors (last 50 lines):")
    print("-" * 40)
    services = ["extractor-discogs", "extractor-musicbrainz", "graphinator", "tableinator", "brainzgraphinator", "brainztableinator"]
    error_found = False
    for service in services:
        try:
            logs = get_service_logs(service, 50)
        except DockerUnavailableError as e:
            print(f"  Docker unavailable: {e}")
            error_found = True
            break
        errors = [line for line in logs.split("\n") if "ERROR" in line or "Failed" in line]
        if errors:
            error_found = True
            print(f"\n  {service}:")
            for error in errors[-5:]:  # Show last 5 errors
                print(f"    {error[:100]}...")

    if not error_found:
        print("  No recent errors found in service logs")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    monitor_system()
