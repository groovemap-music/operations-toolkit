#!/usr/bin/env python3

import sys
import time
from typing import Any

import requests

from utilities import queue_metrics


def get_queue_stats(base_url: str | None = None) -> list[dict[str, Any]] | None:
    """Fetch queue statistics from the RabbitMQ Prometheus endpoint."""
    base_url = base_url or queue_metrics.prometheus_url()
    try:
        return queue_metrics.fetch_queue_metrics(base_url)
    except requests.RequestException:
        print(f"Error connecting to RabbitMQ Prometheus endpoint at {queue_metrics.display_endpoint(base_url)}")
        return None


def _format_rate(rate: float | None) -> str:
    return "-" if rate is None else f"{rate:.2f}"


def monitor_queues(interval: int = 5) -> None:
    """Monitor queue statistics in real-time."""
    print("Monitoring RabbitMQ queues (Press Ctrl+C to stop)...")
    print("-" * 80)

    previous: list[dict[str, Any]] | None = None
    previous_at = 0.0
    try:
        while True:
            queues = get_queue_stats()
            sampled_at = time.monotonic()
            # get_queue_stats() returns None only on a genuine fetch failure
            # (RequestException); an empty list is a successful 200 response from a
            # broker with no queues declared yet (e.g. right after `just up`, before
            # the extractor/consumers connect) and must not be conflated with a
            # connectivity error. This distinction is regression-tested.
            if queues is None:
                print("Failed to fetch queue data")
                time.sleep(interval)
                continue

            print("\033[2J\033[H")
            print(f"RabbitMQ Queue Monitor - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("-" * 80)
            if not queues:
                print("No queues declared yet")
                print("-" * 80)
                time.sleep(interval)
                continue
            rates = queue_metrics.queue_rates(previous, queues, sampled_at - previous_at) if previous is not None else {}
            previous, previous_at = queues, sampled_at
            print(f"{'Queue Name':<50} {'Ready':<10} {'Unacked':<10} {'Total':<10} {'Pub/s':<8} {'Ack/s':<8}")
            print("-" * 100)

            total_messages = 0
            for queue in sorted(queues, key=lambda x: x["name"]):
                name = queue["name"]
                ready = queue.get("messages_ready", 0)
                unacked = queue.get("messages_unacknowledged", 0)
                total = queue.get("messages", 0)
                total_messages += total
                queue_rate = rates.get((queue["vhost"], name), {})
                publish = _format_rate(queue_rate.get("publish"))
                ack = _format_rate(queue_rate.get("ack"))
                line = f"{name:<50} {ready:<10} {unacked:<10} {total:<10} {publish:<8} {ack:<8}"

                if unacked > 0:
                    print(f"\033[93m{line}\033[0m")
                else:
                    print(line)

            print("-" * 100)
            print(f"Total messages across all queues: {total_messages}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped.")


def main() -> None:
    """Run the queue monitor CLI."""
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    monitor_queues(interval)


if __name__ == "__main__":
    main()
