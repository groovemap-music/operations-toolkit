"""Protect the installed command and public Python API contracts."""

from importlib.metadata import distribution

from utilities import catalog_contract, secrets


EXPECTED_COMMANDS = {
    "groovemap-check-errors": "utilities.check_errors:main",
    "groovemap-check-queues": "utilities.check_queues:check_rabbitmq_queues",
    "groovemap-debug-message": "utilities.debug_message:main",
    "groovemap-healthcheck": "utilities.healthcheck:main",
    "groovemap-monitor-queues": "utilities.monitor_queues:main",
    "groovemap-system-monitor": "utilities.system_monitor:monitor_system",
}
CATALOG_FUNCTIONS = {
    "dead_letter_exchange_name",
    "dead_letter_queue_name",
    "entity_types",
    "exchange_name",
    "exchange_prefix",
    "queue_name",
}
CATALOG_CONSTANTS = {
    "CONSUMER_SOURCES",
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "DISCOGS_DATA_TYPES",
    "MUSICBRAINZ_DATA_TYPES",
}


def test_installed_console_entry_points_match_the_supported_commands() -> None:
    entry_points = {
        entry_point.name: entry_point
        for entry_point in distribution("groovemap-operations-toolkit").entry_points
        if entry_point.group == "console_scripts"
    }

    assert {name: entry_point.value for name, entry_point in entry_points.items()} == EXPECTED_COMMANDS
    assert all(callable(entry_point.load()) for entry_point in entry_points.values())


def test_documented_python_api_remains_importable() -> None:
    assert all(callable(getattr(catalog_contract, name)) for name in CATALOG_FUNCTIONS)
    assert all(hasattr(catalog_contract, name) for name in CATALOG_CONSTANTS)
    assert callable(secrets.get_secret)
