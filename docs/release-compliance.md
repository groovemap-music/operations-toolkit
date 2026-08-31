# Release compliance

The repository gate is credential-free and does not contact a deployment. `just check` verifies
formatting, linting, types, tests and coverage, the promoted event contract, the public-content
boundary, immutable automation, package construction and installation, MIT metadata, complete
Git and worktree secret scans, and version consistency. `just audit` adds the current
network-backed Python vulnerability audit.

`just release-dry-run` creates the wheel and source distribution plus SHA-256 checksums, a
CycloneDX SBOM, third-party notices, and provenance containing the exact source revision. It does
not upload a package, create a tag, or change repository settings.

The first-party package is MIT licensed. The release gate verifies the tracked license and package
metadata, then inventories runtime and development dependency licenses with `pip-licenses`.
Dependency vulnerabilities are evaluated from the locked graph with `pip-audit` before a release
is approved.

The CI caller pins the public `groovemap-music/automation` workflow to an immutable commit and uses
one `pull_request` job graph for every author, including Dependabot. Dependabot updates both the
locked Python graph and workflow action pins; no Renovate workflow is active.

Publication remains a separate infrastructure decision. A reviewed green commit, successful
hosted CI, a backed-up source-history rehearsal, and explicit operator approval are required before
any history cutover or visibility change. Release tags and packages require their own approval.
