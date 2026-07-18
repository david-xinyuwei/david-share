# [REVIEW] Fix Pass — 2026-07-18

## Scope

- Repository: `david-xinyuwei/david-share`
- Branch: `master`
- Baseline commit: `97d5237187d1f19d08c8e15fd9d3dec568075537`
- Subtree: `Deep-Learning/MiMo-V2.5-Pro-on-MI300X-Benchmark`
- Review result before fixes: 0 CRITICAL, 4 HIGH, 2 MEDIUM
- Fix policy: only agreed findings; no additional GPU matrix was run

## Agreed Findings and Resolution

| Finding | Resolution | Verification |
|---|---|---|
| HIGH-1: exact64 Decode did not prominently identify fixed acceptance | The English and Chinese READMEs now identify `SGLANG_SIMULATE_ACC_LEN=3` with `match-expected` as a fixed-acceptance performance benchmark. They explicitly state that it does not validate natural MTP acceptance or output quality. | The public analyzer and repository validator enforce the method identity and acceptance boundary. |
| HIGH-2: Prefill length trend mixed independent headline runs | The customer-facing trend now uses the same complete matrix: 8K→64K is +3.3%, and 64K→nominal 256K is -34.0%. Exact 256K remains a separately labeled independent measurement with N=1. | The repository validator rejects the former cross-run causal wording and requires the same-matrix values. |
| HIGH-3: the H200 70.0% number could be read as strict parity | The number is now consistently described as a worksheet-local directional arithmetic ratio. Missing H200 output length, command, repetition count, acceptance method, and Column J scope are disclosed. | The validator requires the qualified wording in both READMEs and machine-readable audit data. |
| HIGH-4: public readers could not independently recompute the exact64 headline | A sanitized evidence pack and `scripts/analyze_exact64_evidence.py` were added. The analyzer verifies the pack manifest, applies the transition guard, and rebuilds 931.58/935.92, 933.75, 743.12, and +25.7%. | Fresh execution returns `status=PASS` and the repository validator executes the analyzer. |
| MEDIUM-1: Prefill headline points lacked fresh-service repetition | Each applicable Prefill point is now explicitly labeled `measurement repetitions=1`; no repeatability claim is made. | The validator requires N=1 disclosure, including the exact 256K record. |
| MEDIUM-2: GitHub Pages failed because of an unrelated parent-repository gitlink | Not changed in this subtree. The README records that CodeQL passed and that Pages is blocked by a pre-existing gitlink without a matching `.gitmodules` URL. | Parent-repository owner action remains required; this does not affect the benchmark data or GitHub README rendering. |

## Numeric Closure

| Claim | Recomputed result | Status |
|---|---:|---|
| Optimized exact64 fresh-service runs | 931.58 / 935.92 scheduler gen tok/s | PASS |
| Optimized mean | 933.75 scheduler gen tok/s | PASS |
| Optimized repeat delta | 0.47% | PASS |
| Same-image exact no-CK baseline | 743.12 scheduler gen tok/s | PASS |
| Optimized bundle uplift | 25.7% | PASS |
| Implied optimized TPOT at BS16 | 17.14 ms | PASS |
| Server-accounted output per repetition | 16,384 tokens | PASS |
| Retokenized generated text per repetition | 4,112 tokens | PASS; not draft accepted tokens |
| H200 worksheet arithmetic ratio | 70.0% | PASS as arithmetic only; strict parity NOT VERIFIED |

## Evidence Boundary

The public evidence pack supports independent recomputation and consistency checking of the disclosed sanitized scheduler windows. It does not independently prove the provenance or completeness of the privately archived full logs. The full-log SHA-256 values remain in the audit metadata, while the public pack intentionally contains only the minimum sanitized material needed to reproduce the published statistic.

## Validation Evidence

The following checks passed after the Fix Pass:

- `python3 scripts/analyze_exact64_evidence.py`
- `python3 scripts/validate_repo.py`
- Python compilation for all files under `scripts/`
- Bash syntax parsing for all files under `scripts/amd-latest/`
- `git diff --check`
- Value-aware public-boundary checks in the repository validator

The generic advisory scanners flag the word `password` in the documented `docker login --password-stdin` flow and in the validator assertion that `password.txt` must not exist. Manual context review confirms these are safe instructions and a negative security assertion, not credential values.

## Final Review Decision

- CRITICAL: 0
- HIGH: 0 open
- MEDIUM: 0 open within this subtree
- External residual: parent-repository Pages configuration

The repository now supports the defensible customer statement that MI300X completed a real exact-64K-input, fixed-acceptance scheduler performance measurement at BS16, with a two-service mean of 933.75 tok/s and a 25.7% improvement over the same-image no-CK baseline. It does not claim natural MTP acceptance, output-quality validation, strict H200 parity, or high-concurrency 128K/256K Decode performance.
