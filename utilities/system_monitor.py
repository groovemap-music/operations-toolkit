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


def check_neo4j_status() -> str:
    """Check Neo4j database status."""
    neo4j_username = os.environ.get("NEO4J_USERNAME", "neo4j")
    neo4j_password = get_secret("NEO4J_PASSWORD", "")
    env = os.environ.copy()
    env["NEO4J_USERNAME"] = neo4j_username
    env["NEO4J_PASSWORD"] = neo4j_password
    try:
        result = docker_run(
            subprocess.run,
            [
                "exec",
                "-e",
                "NEO4J_USERNAME",
                "-e",
                "NEO4J_PASSWORD",
                "groovemap-neo4j",
                "cypher-shell",
                "MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY count DESC LIMIT 10",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
            env=env,
        )
        return result.stdout
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
                "SELECT relname, pg_size_pretty(pg_relation_size(schemaname||'.'||relname)) as size, n_live_tup as rows FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 10;",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        return result.stdout
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
    try:
        containers = get_docker_stats()
    except DockerUnavailableError as e:
        docker_problem = str(e)
        containers = []
    else:
        docker_problem = None
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
