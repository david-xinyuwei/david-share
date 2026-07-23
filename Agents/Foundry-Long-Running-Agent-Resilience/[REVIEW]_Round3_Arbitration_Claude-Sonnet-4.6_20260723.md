# [REVIEW] Round 3 Arbitration — Claude Sonnet 4.6 + Runtime Evidence — 2026-07-23

## Review object

- Repository: `https://github.com/david-xinyuwei/david-share`
- Branch: `master`
- Immutable review commit: `65af8bf1301186f29e2f2ec3061939b763a9356a`
- Subtree: `Agents/Foundry-Long-Running-Agent-Resilience`
- Tree: `1f037a90deb2015e7d9f140a08a1fec80c6e31f3`
- Mode: third-model arbitration followed by deterministic source/runtime adjudication

## Arbitration rule

The third model reviewed the Blue/Red dispute. Its speculative claims were then checked against the immutable source, full CI failure log and executable counterexamples. Where the model report conflicted with measured evidence, measured evidence prevailed.

## Evidence corrections to the third-model draft

1. **CI artifact failure was not a missing-font/Pillow hypothesis.** The full run log shows a JSON artifact being clean-filtered to a Git LFS pointer because the monorepo root tracks every `*.json` with LFS. The target JSON files require a subtree override.
2. **Dependency audit failures were exact `setuptools` findings.** Windows 3.10/3.11 had `setuptools 65.5.0`; Ubuntu 3.11 had `setuptools 79.0.1`; the current fix version for the newest finding is 83.0.0. This is not a Pillow/transitive guess.
3. **The repo does use LFS globally for JSON.** Root `.gitattributes` contains `*.json filter=lfs diff=lfs merge=lfs -text`; target JSON inherited it.
4. **Root README already declares MIT and links `LICENSE`, but that file is missing.** This establishes existing owner intent but leaves the public declaration broken. The fix is to restore the stated MIT file and align package metadata, not choose a new license silently.
5. **Runtime counterexamples confirm continuity weaknesses:**
   - sequence `[10, 12]` produces `monotonic=True` with no gap signal;
   - duplicate sequence `10, 10, 11` produces `monotonic=True` with no duplicate signal;
   - bare `{"type":"done"}` produces `completion_observed=True`;
   - out-of-order `2, 1` alone is detected.
6. **Schema counterexample is definitive.** Eight fake IDs with arbitrary three-field assertions produce zero Draft 2020-12 Schema errors, while the Python validator rejects them.

## Final decisions

| Item | Blue | Red | Runtime/source evidence | Final severity | Agreed fix |
|---|---|---|---|---|---|
| Dedicated CI | HIGH | CRITICAL | Run `29997963707` completed failure: 3 jobs succeeded, 5 failed | **CRITICAL** | Fix JSON LFS attributes and audit environment; retain all gates and require 8/8 green jobs |
| Wheel outside checkout | Understated | CRITICAL | Empty-directory `lra-evidence validate` returns file-not-found | **HIGH** | Make the CLI contract explicit and test supported explicit-path use from an empty directory; do not silently claim standalone bundled evidence |
| Execution provenance | MEDIUM | CRITICAL | Hand-authored conforming assertions can be re-hashed and accepted | **HIGH** | Separate author attestation, deterministic contract validation and artifact integrity; qualify badge/claims; add safe campaign metadata/digests only if export-approved |
| Phase/index set+sorted | PASS | HIGH | Unique lists intentionally summarize coverage but erase duplicate/replay evidence | **MEDIUM** | Preserve existing coverage lists for compatibility and add ordered-sequence diagnostics rather than pretending they prove continuity |
| Sequence gaps/duplicates | PASS | HIGH | `[10,12]` and duplicate values both report monotonic true | **HIGH** | Report strict increase, duplicate count and gaps separately; do not redefine monotonic as contiguous |
| Missing terminal status | Missed | HIGH | Bare `done` reports completed | **HIGH** | Require explicit terminal status; add regression test |
| JSON Schema parity | PASS | HIGH | Adversarial fake matrix yields zero schema errors | **HIGH** | Align Schema to exact eight scenario contracts or explicitly demote it; authoritative public contract should be exact |
| Runtime differential naming | PASS | HIGH | Script reads only synthetic parser fixtures | **MEDIUM** | Rename to fixture/protocol summarizer differential and remove runtime-authenticity implication |
| Public technical depth | PASS | HIGH | Useful validator exists, but major export-safe architecture and campaign lessons are absent | **HIGH** | Add public-safe architecture, protocol ownership, active/suspended work, pattern runbooks, Task Storage onboarding and observer-auth adjudication; withhold private packages/source/IDs |
| Images | PASS | MEDIUM | Clear and correct, but only evidence pipeline and coverage groups | **MEDIUM** | Keep both; add architecture and recovery-sequence visuals using only public concepts and sanitized observations |
| License | HIGH | HIGH | Root declares MIT and links missing `LICENSE`; GitHub reports `license: null` | **HIGH** | Restore the already-declared MIT license at repo root and add package metadata |
| Universal proof chain | PASS | MEDIUM | Workflow/steering contracts do not include failure/reconnect assertions | **HIGH** | Split acceptance sequences by proof pattern in EN/CN docs and README |
| Bilingual validator | PASS | MEDIUM | Bare asserts vanish under `python -O`; structure does not prove semantic parity | **HIGH** | Explicit error collection, deterministic numeric/critical-boundary checks, honest AI audit status |
| Public scanner | PASS | MEDIUM | Finite regex and image variance only | **MEDIUM** | Call it deterministic advisory scanner; supplement with package/history/image manual checks |
| JSON LFS drift | Missed | MEDIUM | Root `*.json` LFS rule converts regenerated target JSON to pointer form | **HIGH** | Add target `.gitattributes` override and CI pointer preflight |
| Dependency audit | Missed | MEDIUM | Old `setuptools` from runner environment triggers known vulnerabilities | **HIGH** | Upgrade packaging tools to a safe version before audit and audit the deliberate clean environment |

## Agreed public export boundary

### Publish

- Current public Hosted Agent concepts from Microsoft Learn.
- Responses versus Invocations ownership and state model.
- Active long-running work versus suspended human approval.
- Pattern-specific evidence requirements and sanitized timelines.
- Service-side preview onboarding/allowlisting as a scoped operational lesson.
- Observer-authentication versus workload-state adjudication.
- Deterministic evidence-contract, integrity and public-boundary tooling.

### Withhold

- Private-preview SDK/package source, package names and private API recipes.
- Raw hosted event payloads and business/model output text.
- Endpoints, response/invocation/session IDs, tenant/subscription/resource IDs.
- Internal collaboration records, names, request IDs and deployment-specific secrets.

## Canonical Fix Pass scope

1. Fast-forward the local monorepo to the unrelated remote changes while preserving this target review.
2. Repair target JSON Git attributes and CI dependency/audit behavior.
3. Rework claims and evidence model so `8/8` is explicitly author-attested campaign status, not independently replayable public proof.
4. Add export-safe technical architecture and pattern-specific runbooks/visuals.
5. Harden event diagnostics, terminal status and Schema parity with adversarial tests.
6. Rename the synthetic parser differential and update all references.
7. Make CLI/wheel behavior truthful and verify it from an empty directory with explicit paths.
8. Replace optimized-away bilingual asserts and strengthen deterministic parity checks.
9. Restore the root MIT file already promised by the root README; align package metadata.
10. Run full local, clean-environment, package, public-boundary, image, bilingual and CI gates; push only after all local gates pass; wait for terminal CI and online rendering.

## Arbitration verdict

- Multi-model review findings have converged after runtime/source correction.
- Current repo: **not L5, not delivery-ready**.
- Agreed Fix Pass: **authorized by the user's instruction to ensure repository quality**.
- No private-preview implementation will be published as part of the fix.
