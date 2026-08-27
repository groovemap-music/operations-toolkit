# Repository instructions

- Keep all default checks credential-free and free of live infrastructure access.
- Operator commands must be observational unless a separately reviewed command clearly says otherwise.
- Never print passwords, tokens, connection strings, or secret-file contents.
- Update the generated queue binding only from the producer commit recorded in
  `contracts/catalog-events/v1/source.json`; run `just contract-check` afterward.
- Run `just check` before proposing a change.
- `just bump` may update local version files only. Publishing, tagging, pushing, and releasing require separate approval.
