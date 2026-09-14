# Operations toolkit coverage policy

The operations toolkit owns a coverage floor measured from this repository's utility package
and unit tests. It is not inherited from the former monorepo or from another GrooveMap service.

## Recorded baseline

The baseline was measured from commit `b7b35b6`:

```text
Python 3.14.5
coverage.py 7.16.0
106 tests passed
499 statements; 496 covered; 3 missed
total line coverage: 496 / 499 = 99.3987975952%
enforced two-decimal floor: 99.39%
```

Run `just coverage` to reproduce the measurement. Coverage collects every test under `tests/`
and measures the complete `utilities` package. It omits only test files and package
`__init__.py` markers. The measured package includes `_transport.py`, `catalog_contract.py`,
`check_errors.py`, `check_queues.py`, `debug_message.py`, `healthcheck.py`,
`monitor_queues.py`, `secrets.py`, and `system_monitor.py`; operator entry points must not be
removed from scope to protect the percentage.

The floor is the baseline truncated conservatively to two decimals. This matches Codecov's
configured `round: down` behavior while remaining below the exact measured result.

## Enforcement

`pyproject.toml` sets `fail_under = 99.39` with two-decimal precision, so `just coverage` and
the coverage recipe within `just check` fail below the floor. The required GitHub Actions job
runs both commands and uploads the same `coverage.xml`; `codecov.yml` applies a fixed 99.39%
project target with no allowed regression threshold.

The workflow has one actor-independent `required` job for every pull request. It contains no
Dependabot or `github.actor` exception, so ordinary and dependency pull requests expose the
same required result. Codecov's patch target remains a complementary signal and cannot relax
the repository-wide floor.

## Ratchet

1. Do not lower the floor to make a change pass. Add tests or remove genuinely unreachable
   code.
2. When a merged change produces a stable higher result, truncate that exact result to two
   decimals and raise `fail_under` and the Codecov project target together.
3. Keep the source, test, and omission scopes unchanged when comparing measurements. An
   intentional scope change must record a new statement count and explain why it is more
   faithful.
4. Keep every operator utility and entry point in scope; never omit a low-coverage module to
   preserve the percentage.
5. Record the baseline commit, tool versions, test count, statement count, covered count, and
   exact result whenever the floor changes.
