# [REVIEW] Round 2 Red Team — GPT-5.5 — 2026-07-23

## Review object

- Repository: `https://github.com/david-xinyuwei/david-share`
- Branch: `master`
- Immutable commit: `65af8bf1301186f29e2f2ec3061939b763a9356a`
- Subtree: `Agents/Foundry-Long-Running-Agent-Resilience`
- Tree: `1f037a90deb2015e7d9f140a08a1fec80c6e31f3`
- Workflow: `.github/workflows/foundry-long-running-agent-resilience-ci.yml`
- Mode: destructive read-only Red Team review; no product files changed

## Executive verdict

Current state is not L5 and is not delivery-ready. It can enter an agreed Fix Pass only after arbitration of Blue/Red differences. Confirmed blockers include failed dedicated CI, a wheel smoke test masked by the checkout, execution provenance that cannot be proven by the public hash chain, event-continuity logic defects, a weak JSON Schema, a mislabeled runtime differential test, missing high-value technical content and unresolved license governance.

## Gate summary

| Gate | Status | Evidence |
|---|---|---|
| Immutable object | PASS | Commit/tree fixed |
| Public boundary | PARTIAL | No obvious secret found; scanner is finite and advisory |
| Agent/Demo authenticity | FAIL | No Hosted runtime implementation in subtree |
| Package/library | FAIL | Empty-directory installed CLI cannot find default matrix |
| Azure claims | PARTIAL | Official links exist; implementation and architecture do not |
| Bilingual | FAIL | Structural asserts disappear under `python -O`; no semantic audit |
| Evidence provenance | FAIL | Hash proves byte integrity, not execution origin |
| CI/clean environment | FAIL | Run `29997963707`: completed/failure, 3 success + 5 failure |
| Images | PARTIAL | Readable, but not sufficient product architecture/evidence visuals |
| License | FAIL | No owner-approved license policy or package metadata |

## External verification

| Claim | Independent check | Verdict |
|---|---|---|
| Hosted Agents support Responses and Invocations | Microsoft Learn Hosted Agents concepts, updated 2026-07-22 | Confirmed |
| Sessions, conversations, background work, agent identity and dedicated endpoints | Microsoft Learn concepts | Confirmed |
| Current Python quickstart uses `azure-ai-projects`, `AIProjectClient`, `DefaultAzureCredential` and Python 3.13+ | Microsoft Learn quickstart, updated 2026-07-21 | Confirmed |
| Target subtree implements Hosted runtime | Full source search | Not found |
| Dedicated CI at immutable commit | GitHub run `29997963707` | Failed |
| Images explain product/LRA architecture | Both PNGs opened | No; they explain only the public evidence pipeline and coverage groups |

## Numeric claims audit

| Claim | Source | Verdict |
|---|---|---|
| 8/8 | Public matrix plus private final summary | Internally consistent; not independently proven by public provenance |
| 18 phases/items | Research records plus private final summary | Consistent only for research patterns |
| 9 artifacts | Manifest: eight records plus generated matrix | Consistent |
| 21 tests | Test collection | Consistent; does not cover key continuity/provenance defects |
| Python 3.10–3.13 | Package metadata and CI matrix | Offline support intent only; immutable CI failed |
| Hosted quickstart Python 3.13+ | Current Microsoft Learn | Must be separated from offline package support |
| CI 3 success / 5 failure | GitHub run `29997963707` | Confirmed |
| 1600×900 images | Actual image inspection and generator | Confirmed dimensions; technical adequacy only partial |
| 2026-07-23 | Matrix date | Campaign date, not cryptographic execution timestamp |

## Findings

### CRITICAL

1. **Dedicated CI is failed**
   - Location: `.github/workflows/foundry-long-running-agent-resilience-ci.yml:45-62`; GitHub run `29997963707`.
   - Impact: the current public SHA cannot be delivery-ready.
   - Fix: repair artifact/LFS and dependency-audit failures without deleting gates; require all eight jobs green.
   - Verify: terminal GitHub Actions conclusion `success`, all matrix jobs successful.
   - Risk: weakening or removing gates would create a false green build.

2. **Wheel/CLI smoke is masked by running inside the source checkout**
   - Location: `src/lra_resilience/cli.py:61-85`, `pyproject.toml:20-23`, workflow wheel steps.
   - Fact: an installed wheel run from an empty directory cannot find `data/validation-matrix.json`.
   - Impact: standalone package behavior is falsely represented.
   - Fix: package the required public resources and resolve them with `importlib.resources`, or require explicit external paths and test that supported contract from an empty directory.
   - Verify: install wheel into a clean environment, `cd` to an empty directory, run documented CLI paths.
   - Risk: duplicating canonical evidence as package data can introduce drift unless generated deterministically.

3. **Public hash chain cannot prove authenticated execution provenance**
   - Location: `scripts/build_public_evidence.py:26-43`, `src/lra_resilience/evidence.py`, `evidence/sanitized-runs/*.json`.
   - Fact: eight hand-authored all-true records with expected shapes can pass builder, validator and manifest generation.
   - Impact: readers can overinterpret `8/8 PASS` and `real-run attestation` as independently verified execution.
   - Fix: explicitly define the author-attested trust model, separate assertion validity from execution provenance, and publish only export-approved provenance metadata or signed attestations. Do not claim that SHA proves execution.
   - Verify: adversarial hand-authored records demonstrate the distinction; README and evidence docs label the trust boundary accurately.
   - Risk: stronger metadata can leak private identifiers if export review is skipped.

### HIGH

1. **Event summarizer destroys order and duplicate information**
   - Location: `src/lra_resilience/events.py:41-44`.
   - Fix: preserve ordered values and report duplicate/reorder/gap information; add negative tests.

2. **Sequence monotonic logic does not detect gaps or duplicates**
   - Location: `src/lra_resilience/events.py:45-63`.
   - Fact: `[10, 12]` and duplicate nondecreasing sequences pass the current check.
   - Fix: report strict increase, duplicates and gaps separately; document protocol-specific guarantees.

3. **Missing terminal status defaults to completed**
   - Location: `src/lra_resilience/events.py:66-75`.
   - Fix: require explicit terminal status or classify it as unknown; add `{"type":"done"}` negative test.

4. **JSON Schema is materially weaker than the Python contract**
   - Location: `data/evidence-contract.schema.json`, `src/lra_resilience/evidence.py`.
   - Fact: Schema accepts arbitrary IDs and weak assertions while Python requires exact IDs, shapes and assertion sets.
   - Fix: generate/author exact conditional schema or label the current file only as a coarse shape schema.
   - Verify: schema-level adversarial payload must fail if the Schema is called authoritative.

5. **`runtime_differential.py` is a synthetic parser differential, not a Hosted runtime differential**
   - Location: `scripts/runtime_differential.py`, `tests/fixtures/*.jsonl`, README quality-gate table.
   - Fix: rename it and all claims; only use `runtime differential` when real runtime inputs/results exist.

6. **Public content is severely impoverished relative to the validated project**
   - Location: README/docs/images overall.
   - Missing export-safe value: framework-agnostic/LangGraph/MAF tiers, Task/Streaming mental model, active work versus suspended HITL, Responses versus Invocations ownership, Task Storage onboarding root cause, observer-auth adjudication, pattern-specific proof chains and source-repair lessons.
   - Fix: add public-safe conceptual architecture, scenario runbooks and timelines without private SDK/package/API recipes, endpoints or IDs.

7. **License governance is unresolved**
   - Location: repository and `pyproject.toml`.
   - Fix: obtain owner approval for monorepo/subtree policy before adding any license; then align file and package metadata. Do not unilaterally add MIT.

### MEDIUM

1. README/methodology imply one universal checkpoint→failure→reconnect chain, but workflow and steering records do not contain that proof. Split acceptance chains by pattern.
2. `scripts/validate_readmes.py` uses `assert`; all checks disappear under `python -O`. Replace with explicit diagnostics and nonzero exit.
3. Bilingual validation is structural only. Add deterministic term/number/scope checks and mark AI semantic/native audit `NOT VERIFIED` unless actually executed with an authorized service.
4. Public scanner is finite regex plus image variance. Position it as advisory; retain manual/image/package/history review.
5. Existing images are readable but do not explain product architecture, protocols, session/conversation state, active/suspended work or Task Storage gating.
6. Artifact gate is exposed to Git LFS pointer/materialized-file drift. Pull LFS correctly or exempt and recommit target small JSON/PNG as normal blobs; reject pointer text in preflight.
7. `pip-audit --local` audits runner/dev packaging tools instead of a locked target set. Audit runtime/dev requirements deliberately in a clean environment.

### LOW

- Replace/remove placeholder-like Schema `$id`.
- Distinguish sanitized runtime attestations from synthetic test fixtures in `scenario-manifest.json`.
- Verify public Author/title wording is explicitly owner-approved.

## Blue Team difference and proposal review

| Blue Team position | Red Team decision | Evidence |
|---|---|---|
| Overall not deliverable / not L5 | Agree | CI, package, provenance and license blockers |
| Images readable/captions correct | Agree, but insufficient | Both images are generic evidence diagrams |
| Accuracy PASS with caveats | Disagree | Public provenance and universal-chain wording are too weak |
| Completeness PASS | Disagree | High-value public-safe technical content is missing |
| Consistency PASS | Disagree | Universal chain conflicts with workflow/steering assertions |
| Security PASS | Narrow to PARTIAL | No obvious leak, but scanner cannot prove comprehensive safety |
| Reproducibility PARTIAL | Agree, raise severity | Empty-directory wheel path fails |
| Provenance Medium | Agree direction, raise severity | Hash cannot prove authenticated execution |
| License High | Agree | Governance decision required; no unilateral MIT |
| Task Storage lesson too generic | Agree | Publish only sanitized allowlist/onboarding lesson |
| Scenario classification ambiguous | Agree | Add explicit sanitized-attestation class |
| Python prerequisite separation | Agree | Offline 3.10+ versus current Hosted quickstart 3.13+ |
| Schema placeholder | Agree, low | Cosmetic compared with schema contract mismatch |

Blue Team factual errors/overclaims:

- Sequence gaps are not detected by the current monotonic check.
- JSON Schema and Python validator are not equivalent.
- Empty-directory wheel behavior was not validated.
- Current dedicated CI is red, not a comprehensive PASS.
- Public completeness and image adequacy were overrated.

## Agreed public-boundary fix plan

1. Reposition honestly as a sanitized evidence and engineering-lessons kit, not an LRA implementation or independently replayable proof.
2. Separate assertion validation, artifact integrity and execution provenance in code/docs/badges.
3. Add export-safe architecture and pattern-specific runbooks covering current public Foundry concepts and sanitized campaign lessons.
4. Publish Task Storage as a scoped service-side onboarding/allowlist lesson without private IDs, endpoints, packages or API recipe.
5. Repair event ordering/gap/terminal logic with negative tests.
6. Align Schema authority with the Python contract.
7. Rename fixture parser differential; never present it as Hosted runtime evidence.
8. Make wheel behavior truthful and test it outside the checkout.
9. Fix LFS/artifact and dependency-audit CI failures; require all eight jobs green.
10. Replace optimized-away bilingual assertions, add deterministic semantic invariants and honest audit status.
11. Keep the public scanner advisory and perform manual/export review.
12. Resolve license policy with explicit owner approval.

## Round 2 verdict

- Current L5: **NO**.
- Current delivery readiness: **NO**.
- Ready for Fix Pass: **only after arbitration of Blue/Red HIGH differences and acceptance of the public export boundary**.
- Security hotfix: no active secret leak identified.
- Round 3: required because the rounds differ on more than three HIGH-level judgments.
