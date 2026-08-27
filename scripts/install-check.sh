#!/usr/bin/env bash
set -euo pipefail

toolkit_tmp="$(mktemp -d)"
trap 'rm -rf "${toolkit_tmp}"' EXIT

uv venv "${toolkit_tmp}/venv"
uv pip install --python "${toolkit_tmp}/venv/bin/python" dist/*.whl
"${toolkit_tmp}/venv/bin/python" -c 'import utilities.catalog_contract; import utilities.secrets'
"${toolkit_tmp}/venv/bin/groovemap-healthcheck" >/dev/null 2>&1 && exit 1 || test "$?" -eq 1
