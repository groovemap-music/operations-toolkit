#!/usr/bin/env python3
"""Check RabbitMQ queue status for all consumer services."""

import time

import requests

from utilities import queue_metrics


def _format_rate(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate:.2f} msg/s"


def check_rabbitmq_queues() -> None:
    """Check the status of all consumer queues in RabbitMQ."""
    base_url = queue_metrics.prometheus_url()
    interval = queue_metrics.sample_interval()

    try:
        first = queue_metrics.fetch_queue_metrics(base_url)
        if not first:
            print("No consumer queues found!")
            return

        started = time.monotonic()
        time.sleep(interval)
        data = queue_metrics.fetch_queue_metrics(base_url)
        rates = queue_metrics.queue_rates(first, data, time.monotonic() - started)
        connections = queue_metrics.consumer_connections()

        if not data:
            print("No consumer queues found!")
            return

        print("Consumer Queue Status:")
        print("=" * 80)

        for queue in data:
            name = queue["name"]
            consumers = queue["consumers"]

            print(f"\nQueue: {name}")
            print(f"  Total Messages: {queue['messages']}")
            print(f"  Ready Messages: {queue['messages_ready']}")
            print(f"  Unacked Messages: {queue['messages_unacknowledged']}")
            print(f"  Active Consumers: {consumers}")

            queue_rate = rates.get((queue["vhost"], name))
            if queue_rate:
                print(f"  Ack Rate: {_format_rate(queue_rate['ack'])}")
                print(f"  Publish Rate: {_format_rate(queue_rate['publish'])}")

            if consumers > 0:
                print("  Consumer Details:")
                if connections is None:
                    print("    Unavailable: could not read consumers from the broker container")
                    continue
                for consumer in connections.get(name, []):
                    print(f"    - Tag: {consumer['consumer_tag']}")
                    print(f"      Connection: {consumer['connection_name']}")

    except requests.ConnectionError:
        print(f"Error: Could not connect to RabbitMQ Prometheus endpoint at {queue_metrics.display_endpoint(base_url)}")
        print("\nMake sure:")
        print("1. RabbitMQ is running (docker-compose up -d)")
        print("2. The rabbitmq_prometheus plugin is enabled")
        print("3. Port 15692 is accessible (or set RABBITMQ_PROMETHEUS_URL)")
    except requests.HTTPError as e:
        # requests types `HTTPError.response` as optional — it is unset when the error
        # is raised without a response attached.
        status = e.response.status_code if e.response is not None else "unknown"
        print(f"Error: HTTP {status} from RabbitMQ Prometheus endpoint")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    check_rabbitmq_queues()
