# Repository instructions

- Keep all default checks credential-free and free of live infrastructure access.
- Operator commands must be observational unless a separately reviewed command clearly says otherwise.
- Never print passwords, tokens, connection strings, or secret-file contents.
- Promote a producer contract and its generated binding only from the commit recorded in
  `contracts/catalog-events/v1/<producer>/source.json`, byte-for-byte; run
  `just contract-check` afterward.
- `utilities/catalog_contract.py` is the hand-authored adapter over both promoted producers.
  Editing it must not change a frozen AMQP identifier in
  `tests/test_catalog_contract_frozen_identifiers.py`.
- Run `just check` before proposing a change.
- `just bump` may update local version files only. Publishing, tagging, pushing, and releasing require separate approval.
