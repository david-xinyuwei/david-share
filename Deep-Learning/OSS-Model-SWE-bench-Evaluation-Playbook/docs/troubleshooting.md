# Problems and Troubleshooting

This guide records the failure modes that most often make an OSS-model SWE-bench run slow, irreproducible, or statistically invalid.

## 1. Generation Is Much Slower Than the Reference

**Symptoms**

- Hundreds of model calls per issue.
- Long trajectories with no patch.
- A low number of active Agent workers despite a healthy model server.

**Likely causes**

- Different mini-swe-agent version.
- Larger `step_limit`, `cost_limit`, or `max_tokens`.
- Different system prompt or tool schema.
- Worker count differs from the reference.

**Fix**

Pin the Agent version, capture the full effective `info.config`, and compare limits and workers field by field. Do not infer equivalence from temperature alone.

**Validate**

Run one canary and compare effective config, API-call count, message count, exit status, and patch size.

## 2. The Config File Looks Correct, but the Effective Config Differs

**Symptoms**

- The YAML matches, but trajectories use a different endpoint, model name, prompt, timeout, or image.

**Likely causes**

- Multiple `-c` files applied in a different order.
- CLI overrides silently replace YAML fields.
- Environment/global configuration is loaded before the run.

**Fix**

Treat trajectory `info.config` as the runtime truth. Run `audit_effective_configs.py`; ignore only intentional per-instance fields such as the task image.

## 3. `docker run` Returns Exit 125

**Symptoms**

- `CalledProcessError` while starting a task container.
- No Agent messages or patch for the instance.

**Likely causes**

- Image pull timeout or registry interruption.
- Docker storage pressure.
- Stale container name.
- Docker daemon instability.

**Fix**

Preserve the failure, check free space and Docker state, pre-pull the exact task image, then rerun only the infrastructure-failed ID. Do not classify it as a model failure.

## 4. Root Disk Fills During Evaluation

**Symptoms**

- `no space left on device`.
- Docker cannot extract layers.
- Evaluation slows sharply or leaves partial images.

**Likely causes**

- SWE-bench task images accumulate on Docker's data root.
- Core dumps or unrelated stopped containers consume the root disk.
- `--clean true` is missing.

**Fix**

Start with the official recommendation of approximately 120GB free storage, use `--clean true`, and delete only artifacts proven unrelated or completed. Never remove an active task image.

## 5. Empty Patch

**Symptoms**

- Prediction exists but `model_patch` is empty.
- Exit status is `RepeatedFormatError` or `LimitsExceeded`.

**Likely causes**

- The Agent never issued the required submit command.
- Tool-call formatting repeatedly failed.
- Step or token limit was reached.

**Fix**

Inspect the trajectory. Count the result as Empty for the frozen run. A retry is a separate phase and must not be silently merged as best-of.

## 6. Temperature 0 Still Produces Different Trajectories

**Symptoms**

- Same issue and config produce different API-call counts, messages, patches, or outcomes.

**Why it happens**

Temperature 0 does not make a multi-turn tool Agent end-to-end deterministic. Backend kernels, request scheduling, ties, tool observations, environment timing, and harness timing can change later turns.

**Fix**

Do not promise byte-identical trajectories. Freeze the method, report run-to-run variability, and use repeated runs only when the statistical contract explicitly calls for them.

## 7. Same Patch, Different Official Outcome

**Symptoms**

- Patch hashes match, but one run passes and another times out or fails.

**Likely causes**

- Harness source differs despite the same package version.
- Task image changed.
- Test timeout, host load, or Docker execution timing changed.

**Fix**

Pin the SWE-bench source commit, task image identity, timeout, namespace, and clean/cache options. Preserve per-instance `report.json` and `test_output.txt`.

## 8. Same SWE-bench Version, Different Scoring Behavior

**Symptoms**

- `pip show` reports the expected version, but specific tasks score differently.

**Likely cause**

The installed distribution and the intended Git commit contain different source files.

**Fix**

Install from the exact commit or mount the checkout through `PYTHONPATH`. The pinned commit used here fixes new-file-only test patches that could otherwise reset the entire working tree.

## 9. Harness Aggregate Appears Outside `--report_dir`

**Symptoms**

- Per-instance reports are under `--report_dir`, but the aggregate JSON appears in the current working directory.

**Fix**

Run the harness from a dedicated evaluation working directory, then locate and hash exactly one aggregate JSON. Do not assume all versions place the aggregate in the same path.

## 10. Installing a Pinned Commit Produces a Broken Harness Import

**Symptoms**

- `pip install git+https://...@<commit>` succeeds.
- Importing the harness fails with `FileNotFoundError` for a non-Python fixture such as a `Cargo.lock` file.

**Cause**

The wheel built from that source revision did not include every runtime fixture used by the harness.

**Fix**

Keep the exact source checkout and install it in editable mode. `scripts/setup_environment.sh` checks out the pinned commit, verifies a known fixture, and runs `pip install -e` so imports resolve fixtures from the source tree.

**Validate**

```bash
bash scripts/setup_environment.sh
python -m swebench.harness.run_evaluation --help
```

## 11. Official Test Timeout

**Symptoms**

- Non-empty patch but no resolved/unresolved `report.json`.
- Test execution reaches the configured timeout.

**Fix**

Keep the timeout outcome as Error unless the frozen protocol defines an infrastructure retry. Do not convert a timeout into Unresolved or retry only because the score is unfavorable.

## 12. One-Direction Differential Retest

**Symptoms**

- Only Reference-Pass/Candidate-Fail cases are retested.

**Why it is invalid**

It can only improve the candidate and cannot observe reverse flips. This is selection bias.

**Fix**

Freeze both directions with `build_dispute_manifest.py`.

## 13. Dynamic Dispute Set Shrinks Between Rounds

**Symptoms**

- Cases that agree after one retest are kept.
- Only remaining disagreements receive another attempt.
- A recomposed score unexpectedly exceeds both original full runs.

**Why it is invalid**

This is optional stopping. Some cases receive more opportunities than others, effectively creating a hidden best-of score.

**Fix**

Return to the original full-run comparison, freeze that dispute set once, and produce exactly one aligned-method outcome for every frozen case. `finalize_frozen_disputes.py` fails if any case is missing or duplicated.

## 14. Sharded Reports Overlap

**Symptoms**

- A merged denominator exceeds the intended set.
- The same instance appears on two nodes.

**Fix**

Use disjoint manifests and `merge_official_reports.py`, which rejects overlapping shards and an incomplete declared denominator.

## 15. A Service Is Active but No Work Is Progressing

**Symptoms**

- Process manager says active, but predictions, reports, or logs do not grow.

**Fix**

Pair lifecycle state with workload evidence: prediction count, report count, active task containers, log mtime, endpoint health, and GPU/model activity. “Active” alone is not progress.

## 16. Hash Manifest Fails Immediately After Creation

**Symptoms**

- `sha256sum -c` fails for a log that is still growing.

**Fix**

Stop all writers first. Generate the manifest only after generation and scoring have fully exited, then verify it before archiving.
