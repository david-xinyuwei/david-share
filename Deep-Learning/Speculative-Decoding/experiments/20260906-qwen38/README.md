# Qwen3.8-27B Deployment Regression (2026-09-06)

English | [中文](README-CN.md) | [Speculative decoding overview](../../README.md)

## Findings and Scope

Run `qwen38-quality-20260906` is an **author-run speculative decoding benchmark and vLLM deployment regression, not a full reproduction of the DFlash paper or a quality certification**. In the matched S stage, `dflash2_7` has the highest observed three-seed median group throughput at each tested concurrency. Scores are broadly close in this subset, but that is not an accuracy guarantee, proof of equivalent answer quality or a formal non-inferiority result.

C/G/S execution covers **69 groups and 1,920 of 5,904 planned responses**. The full campaign remains `BLOCKED`: F accounts for **3,984 responses never executed (`NOT_RUN`)**. The original planned denominator is unchanged.

## Matched S Results

S contains 27 groups: three routes, concurrency 1/4/8, and three seeds. Every group uses the same 64 tasks: 32 HumanEval+ code tasks and 32 MATH-500 tasks. Repeating the same 32 tasks three times does **not** create 96 independent tasks per dataset.

Triples are ordered by seed **20260906, 20260907, 20260908**. Each correctness entry is a count out of 32. Code means HumanEval+; math means MATH-500. Rate and wall-time medians are calculated separately across the three seeds. Length columns contain saved `length_stopped` counts, not percentages.

<!-- BEGIN RESULT_TABLE -->
| Route / concurrency | Median tok/s | Median group wall (s) | Code raw /32 | Code normal /32 | Math raw /32 | Math normal /32 | Code length | Math length |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline / 1 | 53.40 | 3458.61 | 29, 31, 30 | 29, 31, 30 | 30, 30, 30 | 30, 30, 30 | 1, 1, 2 | 2, 1, 2 |
| mtp7 / 1 | 113.34 | 1591.09 | 30, 31, 31 | 30, 31, 31 | 30, 28, 31 | 30, 28, 31 | 2, 1, 1 | 1, 2, 1 |
| dflash2_7 / 1 | 150.51 | 1149.41 | 30, 31, 30 | 30, 31, 30 | 29, 32, 30 | 29, 32, 30 | 2, 1, 2 | 2, 0, 1 |
| baseline / 4 | 190.08 | 1037.22 | 31, 31, 31 | 31, 31, 31 | 30, 31, 30 | 30, 31, 30 | 1, 1, 1 | 1, 0, 2 |
| mtp7 / 4 | 382.85 | 470.35 | 30, 30, 31 | 30, 30, 31 | 29, 29, 29 | 29, 29, 29 | 2, 2, 1 | 2, 1, 2 |
| dflash2_7 / 4 | 451.74 | 377.79 | 31, 31, 29 | 31, 31, 29 | 31, 31, 30 | 31, 31, 30 | 1, 1, 3 | 1, 1, 1 |
| baseline / 8 | 287.72 | 577.44 | 31, 31, 31 | 31, 31, 31 | 30, 29, 30 | 30, 29, 30 | 1, 1, 1 | 2, 2, 2 |
| mtp7 / 8 | 565.24 | 308.08 | 31, 31, 30 | 31, 31, 30 | 29, 29, 30 | 29, 29, 30 | 1, 1, 2 | 2, 1, 1 |
| dflash2_7 / 8 | 741.07 | 249.68 | 31, 31, 30 | 31, 31, 30 | 30, 31, 30 | 30, 31, 30 | 1, 1, 2 | 2, 1, 2 |
<!-- END RESULT_TABLE -->

Source: `matched_summary` in [data/summary.json](data/summary.json). `raw_correct` counts official correct verdicts; `normal_correct` additionally requires `finish_reason=stop`. These fields happen to agree throughout this S slice; neither is replaced by acceptance rate. Length-stopped responses remain in the 32-task denominators.

**Measurement boundary:** group tok/s divides authoritative completion tokens, **including thinking and all answers**, by the entire group's wall time. That clock runs from first measured dispatch to the last terminal receipt, including time spent on wrong or truncated answers. It excludes model download, startup, warmup and grading. It is not isolated GPU decode throughput or time to first token (TTFT).

<!-- BEGIN COUNTEREXAMPLE -->
**Observed counterexample: concurrency 4, seed 20260908. This table uses that individual run, not the three-run medians above.**

| Route | This run's group wall (s) | Normal-correct code /32 | Normal-correct math /32 |
| --- | --- | --- | --- |
| mtp7 | 450.866977 | 31 | 29 |
| dflash2_7 | 484.069949 | 29 | 30 |

DFlash 2 has 3 length-stopped code responses. Using each dataset's `normal_correct / entire group wall time`, the DFlash/MTP normal-correct answer-rate ratios are **0.8713 for code** and **0.9635 for math**. Both are below 1 despite the higher DFlash token rate in this run. This is not a causal diagnosis or evidence that every performance metric improved.
<!-- END COUNTEREXAMPLE -->

![Matched S-stage group throughput](images/throughput.png)

*Figure 1. Author's experiment, run `qwen38-quality-20260906`: concurrency C1/C4/C8, three seeds per route at each concurrency, the same 64 tasks (32 code + 32 math); group tok/s includes thinking. Median with observed min/max across the three seeds, not confidence intervals. Source: [data/groups.json](data/groups.json). Inspect both the observed rate and repeat range.*

## Client Latency

Each route/concurrency row reports the **median of the three per-seed P50 values**, not a pooled percentile across repeated responses. Valid and missing request counts are stated separately for TTFT and TPOT; they count response observations, not independent questions. Missing or undefined observations are not replaced with zero.

<!-- BEGIN LATENCY_TABLE -->
| Route / concurrency | TTFT (ms) | TPOT (ms/token) | E2E (s) | TTFT valid / missing | TPOT valid / missing | E2E valid / missing |
| --- | --- | --- | --- | --- | --- | --- |
| baseline / 1 | 82.727 | 18.567 | 16.359 | 192 / 0 | 192 / 0 | 192 / 0 |
| mtp7 / 1 | 75.127 | 8.011 | 6.236 | 192 / 0 | 192 / 0 | 192 / 0 |
| dflash2_7 / 1 | 80.286 | 5.875 | 6.185 | 192 / 0 | 192 / 0 | 192 / 0 |
| baseline / 4 | 104.008 | 20.104 | 19.035 | 192 / 0 | 192 / 0 | 192 / 0 |
| mtp7 / 4 | 110.259 | 8.549 | 8.661 | 192 / 0 | 192 / 0 | 192 / 0 |
| dflash2_7 / 4 | 115.994 | 6.739 | 5.237 | 192 / 0 | 192 / 0 | 192 / 0 |
| baseline / 8 | 106.598 | 20.845 | 18.457 | 192 / 0 | 192 / 0 | 192 / 0 |
| mtp7 / 8 | 124.699 | 10.041 | 9.915 | 192 / 0 | 192 / 0 | 192 / 0 |
| dflash2_7 / 8 | 124.781 | 7.892 | 7.742 | 192 / 0 | 192 / 0 | 192 / 0 |
<!-- END LATENCY_TABLE -->

Token-based TTFT starts at dispatch and ends at the first nonempty generated `token_ids` event, not an empty role or usage event. Per-request TPOT (time per output token) is `(last_token_time - first_token_time) / (completion_tokens - 1)`, only with more than one completion token and validated token-ID coverage. These are **client delivery** measurements, not GPU-kernel percentiles; a speculative SSE chunk can carry several tokens. Definitions and saved observations are in [evidence/configuration.json](evidence/configuration.json) and [data/groups.json](data/groups.json).

## Recorded Method

The settings below come from the frozen [configuration](evidence/configuration.json) and final [summary](data/summary.json), not current model heads or another experiment. The configuration records intent; observed loading checks are recorded separately in `activation` in [evidence/run.json](evidence/run.json).

| Setting | Recorded value |
|---|---|
| GPU / parallelism | H100 NVL; `tensor_parallel_size=1` |
| Target model | `Qwen/Qwen3.8-27B` |
| Target revision | `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` |
| Draft model | `incoai/Qwen3.8-27B-DFlash2` |
| Draft revision | `dedf8df68adfb1afeaf7b7480c0a0243108177b4` |
| Precision | Target and draft: `bfloat16` |
| Native MTP (Multi-Token Prediction) | Weights shipped in this exact target checkpoint; no separately trained, converted, or community MTP model |
| Required draft architecture | `DFlash2DraftModel` |
| vLLM | `0.28.0`, commit `2cf0a6915ce544dc493a0990f2ea38d81601128a` |
| Matched seeds | `20260906`, `20260907`, `20260908`; `coverage.sampling.seed=20260906` records the base configuration |
| Routes and concurrency | Archived labels `baseline`, `mtp7`, `dflash2_7`; concurrency `1`, `4`, `8` |
| Speculative window | Baseline: 0; MTP and DFlash 2: 7 tokens each |
| Sampling | `temperature=1.0`, `top_p=0.95`, `top_k=20`, `min_p=0.0` |
| Penalties | `presence_penalty=0.0`, `repetition_penalty=1.0` |
| Thinking | `reasoning_effort="xhigh"`; `chat_template_kwargs`: `enable_thinking=true`, `preserve_thinking=true` |
| Limits | `max_completion_tokens=16384`; `max_model_len=32768`; `max_num_seqs=16`; `max_num_batched_tokens=16384` |
| Client dispatch | Closed-loop fixed concurrency over the frozen request order, via loopback beside the server; not identical GPU batch shapes |
| Graders | EvalPlus official sanitize/evaluate CLI, commit `26d6d00bb1fd0fa37f39c99d5290da67891d1c5e`; Math-Verify official `evaluate_model_outputs.py`, commit `ba3d3aaff23b3f4cac7a14672b4f6e293d97c98b` |

The 32 task IDs per dataset were selected by the frozen SHA-256 ordering rule independently of answers and scores. Per-task request seeds are shared across routes; this does not imply aligned random token draws. [Actual request examples](evidence/request-examples.json) retain prompts, payloads and request hashes for `HumanEval/69` and `MATH-500/100` from `S-baseline-c1-s20260906-r1-thinking-mixed`. The analysis preserves archived official-grader verdicts and saved token/timing counters; it does not regrade answers.

Version sources: [target model](https://huggingface.co/Qwen/Qwen3.8-27B/tree/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0), [DFlash 2](https://huggingface.co/incoai/Qwen3.8-27B-DFlash2/tree/dedf8df68adfb1afeaf7b7480c0a0243108177b4), and [pinned vLLM source](https://github.com/vllm-project/vllm/tree/2cf0a6915ce544dc493a0990f2ea38d81601128a).

## Coverage and Completion

All rows belong to `qwen38-quality-20260906` and cover the baseline/MTP/DFlash 2 routes. Stage durations are sums of measured group wall times from [evidence/run.json](evidence/run.json), not GPU allocation time.

| Stage | Completed groups | Executed responses | Measured group wall (s) | Execution status |
|---|---:|---:|---:|---|
| C: compatibility canary | 6 | 48 | 928.508749592 | COMPLETE |
| G: greedy diagnostic | 36 | 144 | 387.088947539 | COMPLETE |
| S: matched subset | 27 | 1,728 | 27800.411325179 | COMPLETE |
| F: full datasets | 0 | 0 | 0 (no execution) | NOT_RUN: 12 groups / 3,984 responses |

Totals are **69/81 groups** and **1,920/5,904 responses**: `48 + 144 + 1728 = 1920` and `1920 + 3984 = 5904`. C/G are not pooled into the S result table. COMPLETE describes execution coverage, not perfect correctness.

The 12 remaining F groups cover all three routes at concurrency 1 and 8, seed 20260906, for HumanEval+ and MATH-500. They are not removed or scored. Before F started, the guard projected **134491.31154072736 seconds**, including a **1.5 safety factor**, against **4628.763888597488 seconds remaining**. The recorded decision is `FULL_MATRIX_DOES_NOT_FIT_BILLING_RUNWAY; denominator unchanged`. This is a projected-admission decision, not a claim that compute ran until the budget was exhausted.

### Recorded Timeline

Selected lifecycle fields from [evidence/run.json](evidence/run.json); the earlier invocations remain visible in [evidence/events.jsonl](evidence/events.jsonl).

![Recorded final invocation and evidence return](images/run-timeline.png)

*Figure 2. Original explanatory diagram generated from this run's recorded events, configuration and request examples. Read the order of work, the blocked full-stage admission, local verification and GPU deallocation; distances are not elapsed-time scale. The exact timestamps remain in the generated log below.*

<!-- BEGIN RUN_LOG -->
```text
last_invocation_start_utc=2026-09-06T06:28:46.633864+00:00 run_id=qwen38-quality-20260906
last_invocation_end_utc=2026-09-06T15:20:08.244046+00:00 phase=BLOCKED completed=1920 total=5904
evidence_verified_utc=2026-09-06T15:22:13Z evidence_verified=true
power_verified_utc=2026-09-06T15:22:53.681726+00:00 power_decision=STOPPED
```
<!-- END RUN_LOG -->

The **last invocation** lasted **31881.610182 seconds**, includes restored earlier groups and nonmeasurement overhead, and is not the campaign's total VM allocation time. It is distinct from the sums of measured group wall times above and from per-request latency. Do not add these different clocks together; total VM allocation time is not reconstructed from this public snapshot.

## Evidence and Replay

| Artifact | What it exposes |
|---|---|
| [source/campaign_runner.py](source/campaign_runner.py) | Archived executed measurement code: group dispatch, measurement clocks and campaign control |
| [source/scoring.py](source/scoring.py) | Archived grading integration and result binding |
| [source/stream_metrics.py](source/stream_metrics.py) | Archived SSE token accounting and client timing definitions |
| [evidence/configuration.json](evidence/configuration.json), [evidence/request-examples.json](evidence/request-examples.json) | Frozen serving/grading contract and two actual request payloads with hashes |
| [evidence/run.json](evidence/run.json), [evidence/events.jsonl](evidence/events.jsonl) | Terminal state, lifecycle timestamps, activation observations and provenance |
| [data/groups.json](data/groups.json), [data/summary.json](data/summary.json) | Public replay input and derived aggregate; each group's `ordered_task_ids` records its input manifest |
| `source_members` in [evidence/run.json](evidence/run.json) | Source-member manifest with bytes and SHA-256; per-group `source` entries in the replay data identify original members |
| [analyze_results.py](analyze_results.py) | Standard-library numerical aggregation; optional figure generation |

These source snapshots document the measurement code archived with the executed campaign. They are **not a complete fresh-GPU provisioning bundle**, nor evidence of a new run. The public projection excludes infrastructure locators and credentials. **Original SSE streams and complete raw answers remain privately archived and are not redistributed here.** The archive SHA-256 and member manifest explain provenance; a hash alone is not standalone proof of runtime behavior.

## Offline Replay

From this directory, use Python 3.10+ and the standard library. No package installation, GPU, network or credentials are required:

```bash
python validate_report.py
python -m unittest discover -p "test_*.py"
```

Both checks should exit with code 0. They validate the saved report/replay contract, not fresh inference or official grading. For optional numerical regeneration:

```bash
python analyze_results.py --groups data/groups.json --output regenerated
```

This reaggregates **saved grades, counts and timing**; it does not generate responses, execute generated answers or regrade them. Compare the output with [data/summary.json](data/summary.json). Add `--figure regenerated/throughput.png` to regenerate the plot. That optional operation uses [Matplotlib 3.10.9](requirements-figures.txt); numerical replay does not. After reviewing source changes, `python validate_report.py --refresh --timeline` regenerates the timeline, report blocks and manifest; the default validator never rewrites evidence. Rendered image bytes can vary with fonts or platform. The [root Quick Start](../../README.md#quick-start) gives the same checks from the parent directory.

## Limits

- No statistical-significance, distribution-equivalence, formal non-inferiority or universal losslessness guarantee follows from these finite repeated tasks.
- Draft acceptance rate is not answer accuracy; `raw_correct`, `normal_correct`, and truncation counts are separate observations.
- The different model/checkpoint/runtime in this run does **not** establish that the [September 5 DFlash concurrent failure](../20260905-quality/README.md) was fixed. Historical results stay separate and unchanged.
- Group throughput and client latency describe different measured boundaries; neither establishes isolated GPU-kernel performance. Public offline replay checks saved evidence, not a newly executed GPU workload.