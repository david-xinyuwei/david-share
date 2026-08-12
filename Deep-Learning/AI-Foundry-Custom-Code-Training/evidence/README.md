# Evidence

Every number quoted in the READMEs comes from one of the files here, or from the failure
text quoted verbatim in [`../docs/troubleshooting.md`](../docs/troubleshooting.md).

## What is here

| File | Contents |
|---|---|
| `training-metrics.jsonl` | One JSON object per completed training step. Every metric the trainer emitted — roughly 80 fields per step, covering loss, KL, advantages, reward, sequence lengths, per-rank balance, memory and MFU. Values are copied verbatim. |
| `validation-baseline.json` | Grader scores from every validation pass, each tagged with the step it ran after. |
| `run-manifest.json` | SHA-256 and record count of the source job log, which steps were captured, and which tool produced the extraction. |
| `run-timeline.md` | Per attempt across the whole investigation: what changed, how long the container ran, where it died. |

The steady-state table in the README is **generated** from `training-metrics.jsonl` by
[`../tools/make_steps_table.py`](../tools/make_steps_table.py), not transcribed. Rerunning
that script against this directory reproduces the table and the aggregate figures the
README quotes in prose.

## Scope of the captured run

`run-manifest.json` records exactly which steps are present. The capture is a console
stream, so it ends where the stream ended rather than where the job ended — if
`stepsCaptured` stops short of `totalStepsPlanned`, the remaining steps ran but were not
recorded on this side, and no claim in the README depends on them.

## What is not here

Runs that failed before the training loop produced no metrics, so they have no rows. Their
signatures are in [`../docs/troubleshooting.md`](../docs/troubleshooting.md), quoted from
the job logs that produced them, with the file and line of the failing call.

The memory split in the README is partly derived rather than fully instrumented: the actor
figure is measured (`perf/max_memory_reserved_gb` in `training-metrics.jsonl`), while the
vLLM and KV-cache figures follow from the configured `gpu_memory_utilization` and the model
size. That distinction is stated where the table appears.

## What is removed, and why

[`../tools/extract_training_evidence.py`](../tools/extract_training_evidence.py) redacts
run GUIDs, container scratch paths, registry coordinates, job names and IP addresses on the
way out. None of these change a signature or a conclusion; all are specific to one
subscription. No numeric value is altered, so these files can be diffed directly against a
rerun on other hardware.
