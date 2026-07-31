# SWE-bench Evaluation Best Practices

This document defines the benchmark contract used by this repository. The default path applies to open-source models exposed through an OpenAI-compatible endpoint with function tool calls.

## 1. Treat Generation and Scoring as Separate Systems

SWE-bench evaluation has two independent planes:

1. **Agent generation**: mini-swe-agent receives the issue and repository, calls the model, uses shell tools, and produces a patch plus trajectory.
2. **Official scoring**: the SWE-bench harness applies the patch in the task image and runs the authoritative tests.

An HTTP 200 from the model endpoint proves neither that the patch is valid nor that the official tests pass. Preserve separate logs, run IDs, configs, and manifests for the two planes.

## 2. Freeze the Execution Contract Before the First Case

Record these fields before generation:

| Surface | Freeze |
|---|---|
| Dataset | Repository, split, row count, dataset revision if available |
| Agent | mini-swe-agent tag or wheel hash |
| Agent config | YAML SHA-256 and complete config order |
| Python environment | `pip freeze` output and SHA-256 |
| Model | Public model ID, weight revision, served model name |
| Endpoint | API shape and non-secret base URL pattern |
| Sampling | Temperature, top-p, maximum output tokens |
| Agent limits | Step, cost and wall-time limits |
| Concurrency | Generation worker count |
| Harness | SWE-bench commit, namespace, timeout, cache level, clean mode and worker count |
| Inputs | Full instance manifest SHA-256 |

Version labels are not enough. A package can report the same release while individual source files differ. When a particular commit matters, import the checked-out source or build an immutable environment from that commit.

Pass secrets through the provider's environment-variable contract. For the `hosted_vllm` LiteLLM provider used here, use `HOSTED_VLLM_API_KEY`; never put a real key in a YAML file or `-c key=value` process argument.

## 3. Run a Canary Before the Full Set

A canary should prove all of the following:

- The endpoint returns the expected served model.
- mini-swe-agent writes a trajectory and prediction.
- `info.config` contains the intended effective configuration.
- A non-empty patch can reach the official harness.
- The official harness produces a `report.json` and aggregate report.
- All temporary task containers are removed.

Do not promote a canary merely because generation completed. The scoring plane must also pass.

## 4. Validate Every Generation Artifact

For each planned instance, require:

- One prediction entry.
- One parseable trajectory.
- A known terminal status such as `Submitted`, `LimitsExceeded`, `TimeExceeded`, or `RepeatedFormatError`.
- A complete effective Agent config.
- Explicit classification of empty patches.

Use `scripts/validate_predictions.py` immediately after generation. An infrastructure exception is not a model failure and must not silently enter the denominator as an unresolved patch.

## 5. Retry Infrastructure Failures, Not Model Outcomes

Safe retry examples:

- Docker registry timeout.
- Image pull interruption.
- Docker daemon restart.
- Host disk recovery before the task container started.

Do not retry these merely because the outcome is unfavorable:

- Official test failure.
- Empty patch caused by Agent limits.
- `LimitsExceeded` with a valid trajectory.
- A submitted patch that fails tests.

Record the original infrastructure failure, pre-pull the exact image if needed, and rerun only the affected IDs under the same frozen config. Never turn retries into best-of scoring.

## 6. Freeze Differential Retests Once

When two complete runs disagree:

1. Normalize each outcome to Pass or Not-Pass.
2. Freeze both directions before any retest:
   - Reference Pass / Candidate Not-Pass.
   - Candidate Pass / Reference Not-Pass.
3. Hash the manifest.
4. Run every frozen dispute exactly once under the new method.
5. Retain uncontested baseline outcomes and replace all frozen disputes together.

Never shrink the dispute set after an intermediate retest. Stopping cases when they happen to agree while giving the remaining cases another attempt is optional stopping and inflates the recomposed score. `finalize_frozen_disputes.py` rejects partial or overlapping retest sets.

Pass the declared denominator through `--expected-count` when freezing, merging, or finalizing reports. Equal ID sets are not sufficient: two reports can be identically incomplete.

## 7. Keep Multi-Phase Data Isolated

Use separate directories for:

- `canary/`
- `full-generation/`
- `official-eval/`
- `infrastructure-retry/`
- `frozen-dispute-retest/`

Do not overwrite a full-run prediction with a retest prediction. Link phases through hashes and explicit lineage fields.

## 8. Seal Evidence After Writers Stop

Create manifests only after generation and harness processes have exited. Hashing a growing log produces an immediately stale manifest.

Recommended order:

1. Confirm process/unit completion.
2. Confirm no task containers remain.
3. Validate ID coverage and outcome categories.
4. Create `SHA256SUMS.txt`.
5. Verify the manifest locally.
6. Archive and hash the outer archive.

## 9. Report Scope Before the Number

Every score must state:

- Dataset and split.
- Denominator.
- Whether it is a clean full run or frozen-dispute replacement.
- Retry policy.
- Empty and error counts.
- Agent and harness versions.

A targeted subset hit rate is not a full-benchmark accuracy. A frozen-dispute replacement score is valid only when the original dispute set is complete and each disputed case contributes exactly one targeted result.

## 10. Public Repository Boundary

Public examples must use placeholders and public model IDs. Never commit private endpoints, IP addresses, credentials, customer data, internal image registries, local absolute paths, or private benchmark artifacts.
