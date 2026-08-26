# Evidence

`live-validation.json` is a sanitized summary of a real Windows service validation run. It records the tested runtime contract and removes all tenant, subscription, resource, endpoint, account, and credential values.

`publication-validation.json` is generated after the public tree is packaged and the frozen executable passes its non-mutating self-check. It binds that result to an aggregate source-tree hash, the monorepo workflow hash, package hash/size, self-check hash, and dependency versions. The package itself is not published.

`scenario-screenshots.json` binds four scenario screenshots to their SHA-256 digests, dimensions, source timestamps, tools, observed results, and scenario-specific privacy transformations. The private recording is not published. The manifest fails closed if any screenshot is missing or if the four privacy assertions permit a human image/avatar, email/account identifier, desktop directory/filename, or local path.

The exact model version is derived from Azure Resource Manager deployment metadata; only the model family/version and verification method are retained. No request ID is claimed because none is available in the sanitized record.

The public repository does not include raw runtime logs because those logs can contain local paths, account identifiers, service endpoints, camera artifacts, or message content. Deterministic CI recomputes source, README, customer-page, scenario, refusal-path, and packaged self-check contracts from the committed tree. The workflow is intentionally stored at the public monorepo root: `../../../.github/workflows/voice-live-aipc-ci.yml`.

Evidence labels:

- `dynamic-runtime`: a real external service or Windows device path.
- `test-fixture`: deterministic contract validation with no live-service claim.
- `sanitized-runtime-summary`: facts derived from a live run after private identifiers were removed.

This evidence supports the exact checks stated in the JSON. It does not certify production readiness, SLA, model quality, or universal hardware compatibility.
