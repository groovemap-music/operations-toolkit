"""Validate current first-party license and package metadata."""

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
with (ROOT / "pyproject.toml").open("rb") as source:
    project = tomllib.load(source)["project"]

assert project["license"] == "MIT"
assert project["name"] == "groovemap-operations-toolkit"
license_text = (ROOT / "LICENSE").read_text()
assert license_text.startswith("MIT License\n")
assert "Permission is hereby granted, free of charge" in license_text
