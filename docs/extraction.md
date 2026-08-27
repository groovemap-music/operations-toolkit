# History-preserving extraction

The source was the migration branch `wt/bead/issue/discogsography-2kpm.18` at
`dd6f5d693d8a16a486894687356768bb91c7514f` in the unchanged monorepo
`/Users/Robert/workspaces/github/SimplicityGuy/discogsography`.

The reproducible extraction was performed in a disposable clone:

```bash
git clone --no-local --single-branch \
  --branch wt/bead/issue/discogsography-2kpm.18 \
  /Users/Robert/workspaces/github/SimplicityGuy/discogsography \
  operations-toolkit
cd operations-toolkit
git filter-repo --force \
  --path utilities/ \
  --path tests/utilities/ \
  --path LICENSE \
  --path-rename tests/utilities/:tests/
git branch -M main
```

The filter retained 35 relevant commits and no tags. The current repository removes the
former monorepo-relative runtime import used only for secret-file reading. Queue names and
entity vocabulary remain an exact copy of the producer-owned contract, pinned to an
immutable `catalog-ingestion` commit.

The original monorepo and its refs were not rewritten or deleted.
