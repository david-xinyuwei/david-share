# [REVIEW] Round 1 — Claude Opus 4.6 — 2026-07-23

## Review object

- Repository: `https://github.com/david-xinyuwei/david-share`
- Branch: `master`
- Immutable commit: `65af8bf1301186f29e2f2ec3061939b763a9356a`
- Subtree: `Agents/Foundry-Long-Running-Agent-Resilience`
- Tree: `1f037a90deb2015e7d9f140a08a1fec80c6e31f3`
- Workflow: `.github/workflows/foundry-long-running-agent-resilience-ci.yml`
- Mode: read-only Blue Team review; no product files changed

## Applicable gates

Public Repo, Agent/Demo authenticity, Python package, Azure product claims, bilingual delivery, evidence provenance, clean environment, Git/CI/online validation.

## External verification

| Claim | Verification | Round 1 verdict |
|---|---|---|
| Hosted Agents support Responses and Invocations | Microsoft Learn Hosted Agents concepts, updated 2026-07-22 | Confirmed |
| Hosted Agents provide sessions, conversations, background work and agent identity | Microsoft Learn concepts/quickstart | Confirmed |
| Python deployment workflow uses current Foundry SDK/azd paths | Microsoft Learn quickstart | Public repo intentionally does not ship this implementation |
| License | No LICENSE found in target or repo root | High blocker |
| Images | Both PNG files opened and visually inspected | Readable, captions match |

## Seven-dimensional review

| Dimension | Round 1 verdict | Notes |
|---|---|---|
| Accuracy | PASS with caveats | 8/8 agrees with private final summary |
| Completeness | PASS | Eight documented records are present |
| Consistency | PASS | EN/CN structure and matrix are internally aligned |
| Timeliness | Medium risk | Product guidance may drift |
| Security | PASS | No obvious public leak found |
| Reproducibility | PARTIAL | Offline validator is reproducible; hosted campaign is not public |
| Provenance | Medium risk | Attestations are self-declared; SHA only locks committed bytes |

## Reader perspectives

- Decision-maker: can see the 8/8 result and boundary quickly, but cannot independently reproduce the hosted campaign.
- Engineer: can run the offline CLI but not the actual Hosted Agent scenarios.
- Auditor: can verify hashes and schema, but cannot prove the original run from public artifacts alone.
- Beginner: Quick Start is readable; the distinction between validating records and validating Hosted Agent behavior should be even more explicit.

## Numeric claims audit

| Claim | Source | Round 1 verdict |
|---|---|---|
| 8/8 | Eight public records plus private final summary | Consistent |
| 18 phases/items | Four research assertions and private final summary | Consistent |
| 9 artifacts | Manifest: eight records plus generated matrix | Consistent |
| 21 tests | Local pytest count | Consistent |
| Python 3.10–3.13 | Package metadata and CI matrix | Consistent for offline kit |
| 2026-07-23 validation date | Matrix and private final run | Consistent |

## Findings

### HIGH

1. **Missing license**
   - Files: repository root and target subtree.
   - Fact: no LICENSE file or package license metadata.
   - Impact: reuse terms are legally ambiguous.
   - Proposed fix: add an owner-approved license and matching package metadata.
   - Verification: repository license metadata, wheel metadata and link checks.
   - Risk: choosing a license without owner approval can incorrectly relicense existing monorepo content.

### MEDIUM

1. **Public positioning cannot independently prove provenance**
   - Files: `README.md`, `evidence/README.md`, `evidence/sanitized-runs/*.json`.
   - Fact: `source_kind` is an author assertion; SHA-256 proves integrity after publication, not source authenticity.
   - Proposed fix: strengthen the trust-model statement and do not describe hashes as proof of execution.
   - Verification: adversarially hand-author an all-true record and confirm current builder accepts it.
   - Risk: excessive disclosure could cross the private-preview boundary.

2. **Task Storage onboarding lesson is too generic**
   - Files: `docs/failure-modes.md`, `docs/failure-modes-CN.md`.
   - Fact: private campaign established a service-side Task Storage allowlist/onboarding cause, while public text says only service onboarding.
   - Proposed fix: publish a sanitized, scoped lesson without subscription, project, request or internal package details.
   - Verification: public-boundary scan and bilingual semantic review.
   - Risk: private-preview entitlement details must not be framed as a public self-service feature.

3. **Scenario-manifest classification is ambiguous**
   - File: `scenario-manifest.json`.
   - Fact: committed real-run derivatives are classified as test fixtures.
   - Proposed fix: distinguish `sanitized-runtime-attestation` from synthetic parser fixtures and update validators/docs.
   - Verification: scenario-manifest tests and public validator.
   - Risk: adding a new class without updating every consumer causes CI drift.

4. **Offline Python support and current Hosted deployment prerequisites need separation**
   - Files: `README.md`, `README-CN.md`, `pyproject.toml`.
   - Proposed fix: state that Python 3.10+ applies only to the offline validator; Hosted deployment prerequisites come from current official quickstart.
   - Verification: official-source links and bilingual gate.

5. **Schema identifier is placeholder-like**
   - File: `data/evidence-contract.schema.json`.
   - Proposed fix: remove or replace `https://example.invalid/...`.

### LOW

- Clarify that the matrix is generated while the JSON Schema is authored.
- Document manifest build order.
- Clarify deterministic image generation across platforms.
- Keep conservative Azure GUID scanning unless a demonstrated false positive exists.

## Content disposition

### Preserve

- Six-level evidence hierarchy.
- Public/private boundary statement.
- Eight-scenario coverage table.
- Offline CLI, manifest, parser and fail-closed validation code.
- Both reviewed diagrams.
- Failure-mode adjudication structure.

### Adjust

- 8/8 claim strength and provenance language.
- Task Storage lesson.
- Scenario-manifest classification.
- Python prerequisite scope.
- License and package metadata.

### Withhold

- Private-preview SDK/package source.
- Endpoint, identity, subscription, project and raw hosted payload data.
- Internal collaboration records and deployment recipes that expose private implementation details.

## Proposed fix plan

1. Establish an owner-approved license decision.
2. Reposition the project explicitly as an offline public evidence/knowledge kit, not a runnable LRA implementation.
3. Strengthen provenance limitations and add derived evidence metadata that is safe to publish.
4. Publish a sanitized technical architecture and protocol/session/conversation mapping based only on current public Microsoft Learn facts.
5. Add sanitized runbooks and event timelines for each proof pattern without private package/API details.
6. Correct scenario classification, Schema authority, bilingual validator and package-data behavior.
7. Repair CI, then run clean clone/wheel/CLI/public-boundary/online checks.

## Round 1 verdict

- Deliverable today: **NO**.
- L5: **NO** until license, provenance positioning, package/CI and public knowledge gaps are resolved.
- Security hotfix: none identified.
- Ready for independent Red Team: **YES**.
- Blue Team overall view: the offline validator and methodology are worth preserving, but the public trust model and delivery details require hardening.
