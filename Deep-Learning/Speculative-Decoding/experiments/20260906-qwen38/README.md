# Qwen3.8-27B: MTP and DFlash 2 Measurements

With seven draft candidates each, how much faster is DFlash 2 than native MTP? Are those faster responses still correct? This run used the same code and math tasks on one H100 NVL to measure speed, scores and length stops together.

DFlash 2 exceeded MTP7 in output throughput across all nine matched concurrency/seed pairs. Scores were broadly close, but at concurrency 4 in the third run, DFlash 2 answered **29/32** code tasks correctly versus **31/32** for MTP7, and took longer to finish that group. **The throughput advantage was observed; non-decreasing accuracy was not established.**

This is an author-run vLLM deployment test, not a full reproduction of the DFlash paper. The reported comparison repeats the same 64 tasks. The full-dataset phase was not executed; see [coverage](#coverage-and-unexecuted-work).

> Author: Xinyu Wei (魏新宇)

[English](README.md) | [中文](README-CN.md) | [Speculative decoding overview](../../README.md)

[Results](#throughput-and-answer-quality) · [Latency](#client-latency) · [Method](#test-method) · [Coverage](#coverage-and-unexecuted-work) · [Offline Replay](#offline-replay)

Run date: 2026-09-06. Run ID: `qwen38-quality-20260906`.

---

<a id="matched-s-results"></a>

## Throughput and Answer Quality

Three routes used the same 32 HumanEval+ code tasks and 32 MATH-500 tasks at concurrency 1, 4 and 8, with three seeds each: 27 groups. **Repeating 32 tasks three times does not create 96 independent tasks per dataset.**

The baseline has no speculation; MTP7 and DFlash 2-7 each use seven draft tokens. Throughput and group wall time are separately summarized by their three-run medians. Triples in the score and length-stop tables are ordered by seed **20260906, 20260907, 20260908**. Each score is out of 32.

![Output throughput at concurrency 1, 4 and 8](images/throughput.png)

*Figure 1. Author's measurements. Bars show medians of three runs; whiskers show observed minima and maxima, not confidence intervals. The same 64 tasks are used throughout; throughput includes thinking tokens. Source: [group records](data/groups.json).*

<!-- BEGIN RESULT_TABLE -->
### Throughput and Group Duration

| Concurrency | Route | Output tok/s | Group wall (s) |
| --- | --- | --- | --- |
| 1 | Baseline | 53.40 | 3458.61 |
| 1 | MTP7 | 113.34 | 1591.09 |
| 1 | DFlash 2-7 | 150.51 | 1149.41 |
| 4 | Baseline | 190.08 | 1037.22 |
| 4 | MTP7 | 382.85 | 470.35 |
| 4 | DFlash 2-7 | 451.74 | 377.79 |
| 8 | Baseline | 287.72 | 577.44 |
| 8 | MTP7 | 565.24 | 308.08 |
| 8 | DFlash 2-7 | 741.07 | 249.68 |

### Code and Math Scores

| Concurrency | Route | Code correct /32 | Math correct /32 |
| --- | --- | --- | --- |
| 1 | Baseline | 29, 31, 30 | 30, 30, 30 |
| 1 | MTP7 | 30, 31, 31 | 30, 28, 31 |
| 1 | DFlash 2-7 | 30, 31, 30 | 29, 32, 30 |
| 4 | Baseline | 31, 31, 31 | 30, 31, 30 |
| 4 | MTP7 | 30, 30, 31 | 29, 29, 29 |
| 4 | DFlash 2-7 | 31, 31, 29 | 31, 31, 30 |
| 8 | Baseline | 31, 31, 31 | 30, 29, 30 |
| 8 | MTP7 | 31, 31, 30 | 29, 29, 30 |
| 8 | DFlash 2-7 | 31, 31, 30 | 30, 31, 30 |

All answers marked correct by the graders stopped normally in this run, so raw-correct and normal-stop-correct counts coincide. Both fields remain in the data; duplicate columns are omitted here.

<details>
<summary>Length stops across the three runs</summary>

| Concurrency | Route | Code length stops | Math length stops |
| --- | --- | --- | --- |
| 1 | Baseline | 1, 1, 2 | 2, 1, 2 |
| 1 | MTP7 | 2, 1, 1 | 1, 2, 1 |
| 1 | DFlash 2-7 | 2, 1, 2 | 2, 0, 1 |
| 4 | Baseline | 1, 1, 1 | 1, 0, 2 |
| 4 | MTP7 | 2, 2, 1 | 2, 1, 2 |
| 4 | DFlash 2-7 | 1, 1, 3 | 1, 1, 1 |
| 8 | Baseline | 1, 1, 1 | 2, 2, 2 |
| 8 | MTP7 | 1, 1, 2 | 2, 1, 1 |
| 8 | DFlash 2-7 | 1, 1, 2 | 2, 1, 2 |

Length-stopped responses remain in each 32-task denominator.

</details>
<!-- END RESULT_TABLE -->

These tables are generated from the [saved summary](data/summary.json). Throughput is server-confirmed output tokens divided by entire-group wall time, **including thinking, wrong answers and length stops**. Timing runs from first measured dispatch to the last terminal receipt, excluding downloads, startup, warmup and grading. It is not isolated GPU decode throughput.

### Why Correct-Answer Delivery Also Matters

<!-- BEGIN COUNTEREXAMPLE -->
**Observed counterexample: concurrency 4, seed 20260908. This table uses that individual run, not the three-run medians above.**

| Route | This run's group wall (s) | Normal-correct code /32 | Normal-correct math /32 |
| --- | --- | --- | --- |
| MTP7 | 450.87 | 31 | 29 |
| DFlash 2-7 | 484.07 | 29 | 30 |

DFlash 2 has 3 length-stopped code responses. Using each dataset's `normal_correct / entire group wall time`, the DFlash/MTP normal-correct answer-rate ratios are **0.8713 for code** and **0.9635 for math**. Both are below 1 despite the higher DFlash token rate in this run. This is not a causal diagnosis or evidence that every performance metric improved.
<!-- END COUNTEREXAMPLE -->

## Client Latency

TTFT measures the wait for the first output token. TPOT measures mean delivery time per output token after the first. Response time runs from dispatch to terminal receipt. All three are client observations; lower values are better.

Each configuration reports the **median of the three per-run P50 values**, not a single percentile pooled across all responses. Missing or undefined values are not replaced with zero.

<!-- BEGIN LATENCY_TABLE -->
### Time to First Token (ms)

| Concurrency | Baseline | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 82.727 | 75.127 | 80.286 |
| 4 | 104.008 | 110.259 | 115.994 |
| 8 | 106.598 | 124.699 | 124.781 |

### Time per Output Token (ms/token)

| Concurrency | Baseline | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 18.567 | 8.011 | 5.875 |
| 4 | 20.104 | 8.549 | 6.739 |
| 8 | 20.845 | 10.041 | 7.892 |

### Response Time (s)

| Concurrency | Baseline | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 16.359 | 6.236 | 6.185 |
| 4 | 19.035 | 8.661 | 5.237 |
| 8 | 18.457 | 9.915 | 7.742 |

Each metric in each configuration has 192 valid response observations and 0 missing observations. These are repeated responses, not independent tasks.
<!-- END LATENCY_TABLE -->

<details>
<summary>Exact latency definitions</summary>

TTFT starts at dispatch and ends at the first nonempty generated `token_ids` event, not an empty role or usage event. TPOT is `(last_token_time - first_token_time) / (completion_tokens - 1)`, only with more than one completion token and validated token-ID coverage.

A speculative SSE chunk can carry several tokens. These are client delivery measurements, not GPU-kernel execution times. See the [configuration](evidence/configuration.json) for definitions and [group records](data/groups.json) for observations.

</details>

<a id="recorded-method"></a>

## Test Method

The three routes keep the target model, precision, tasks, output budget and sampling fixed while switching speculative configuration. Settings come from the [saved configuration](evidence/configuration.json); observed loading checks are in `activation` in the [run evidence](evidence/run.json).

| Setting | This run |
|---|---|
| Hardware | One H100 NVL; tensor parallelism 1 |
| Target | Qwen3.8-27B, BF16 |
| MTP | Native weights in the target checkpoint; not separately trained or converted |
| DFlash 2 | incoai's Qwen3.8-27B-DFlash2, BF16 |
| Engine | vLLM 0.28.0; Model Runner V2 observed loading |
| Candidates | Baseline: 0; MTP7 and DFlash 2-7: 7 each |
| Output budget | At most 16,384 tokens per task, including thinking |
| Thinking | Enabled and preserved; `reasoning_effort="xhigh"` |
| Sampling | temperature 1.0, top_p 0.95, top_k 20 |
| Pairing | Concurrency 1, 4, 8; seeds 20260906, 20260907, 20260908 |

The 32 task IDs per dataset were selected by a frozen SHA-256 ordering rule, independently of answers and scores. Routes share per-task seeds, which does not imply aligned random draws at every token. Code was graded by the official EvalPlus tools; math by the official Math-Verify tool.

<details>
<summary>Pinned versions, full parameters and request examples</summary>

These links identify the actual versions used, not current model repository heads:

| Component | Pinned record |
|---|---|
| Target | [Qwen3.8-27B checkpoint](https://huggingface.co/Qwen/Qwen3.8-27B/tree/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0) |
| DFlash 2 | [Qwen3.8-27B-DFlash2 checkpoint](https://huggingface.co/incoai/Qwen3.8-27B-DFlash2/tree/dedf8df68adfb1afeaf7b7480c0a0243108177b4), architecture `DFlash2DraftModel` |
| vLLM | [0.28.0 source](https://github.com/vllm-project/vllm/tree/2cf0a6915ce544dc493a0990f2ea38d81601128a) |
| EvalPlus | [Pinned source](https://github.com/evalplus/evalplus/tree/26d6d00bb1fd0fa37f39c99d5290da67891d1c5e), official sanitize/evaluate CLI |
| Math-Verify | [Pinned source](https://github.com/huggingface/Math-Verify/tree/ba3d3aaff23b3f4cac7a14672b4f6e293d97c98b), official `evaluate_model_outputs.py` |

Remaining settings: `min_p=0.0`, `presence_penalty=0.0`, `repetition_penalty=1.0`. The template sets `enable_thinking=true` and `preserve_thinking=true`. Scheduling limits are `max_model_len=32768`, `max_num_seqs=16`, `max_num_batched_tokens=16384`.

Client and server run on the same machine, with closed-loop fixed-concurrency dispatch over loopback in the frozen request order. Equal client concurrency does not imply identical GPU batch shapes. Archived route labels are `baseline`, `mtp7`, `dflash2_7`; the base configuration seed is 20260906.

[Request examples](evidence/request-examples.json) retain prompts, full payloads and hashes for `HumanEval/69` and `MATH-500/100` from the first baseline group. `raw_correct` records official correct verdicts; `normal_correct` also requires `finish_reason=stop`. They happen to agree in this S stage. Offline analysis uses saved grades and does not regrade answers.

</details>

<a id="coverage-and-completion"></a>

## Coverage and Unexecuted Work

The original plan has four stages. Performance and score tables in this report use only S. Compatibility and greedy diagnostics are not pooled into the formal subset comparison.

| Stage | Completed groups | Responses | Status |
|---|---:|---:|---|
| C: compatibility | 6 | 48 | Complete |
| G: greedy diagnostics | 36 | 144 | Complete |
| S: repeated subset | 27 | 1,728 | Complete |
| F: full datasets | 0 | 0 | Not run |

Totals are **69/81 groups and 1,920/5,904 responses**. The remaining 12 groups and 3,984 responses stay `NOT_RUN`: neither removed from the plan nor marked incorrect. The campaign's recorded overall state therefore remains `BLOCKED`.

F would run all three routes at concurrency 1 and 8 over all 164 HumanEval+ and 500 MATH-500 tasks, once per task, with seed 20260906. Before admission, the guard projected about **37.36 hours** including a 1.5 safety factor, with about **1.29 hours** remaining. F was not started; it did not run until the budget was exhausted.

Exact projections and the reason remain in [run evidence](evidence/run.json): `FULL_MATRIX_DOES_NOT_FIT_BILLING_RUNWAY; denominator unchanged`.

<details>
<summary>Measured duration by stage</summary>

| Stage | Sum of group wall times (s) |
|---|---:|
| C | 928.51 |
| G | 387.09 |
| S | 27,800.41 |
| F | 0, not run |

These are sums of measured group wall times, rounded to two decimals; exact values remain in [run evidence](evidence/run.json). They are not total VM allocation time. Complete describes execution, not perfect correctness.

</details>

### Recorded Timeline

After execution, evidence was collected and verified locally before GPU deallocation. Milestones come from the [run record](evidence/run.json); earlier invocations remain in the [event log](evidence/events.jsonl).

![Recorded final invocation and evidence return](images/run-timeline.png)

*Figure 2. Generated from recorded events, configuration and request examples. It shows execution, blocked full-stage admission, evidence collection and GPU deallocation in order; spacing does not represent elapsed time.*

<!-- BEGIN RUN_LOG -->
| Milestone | Time (UTC) |
| --- | --- |
| Final invocation starts | 2026-09-06 06:28:46 |
| Execution ends; full stage not started | 2026-09-06 15:20:08 |
| Local evidence verified | 2026-09-06 15:22:13 |
| GPU deallocated | 2026-09-06 15:22:53 |

**1,920/5,904 responses** were complete at the end. Times are displayed to seconds; full timestamps, execution state and closure records remain in [run evidence](evidence/run.json).
<!-- END RUN_LOG -->

The final invocation lasted about **8 hours 51 minutes**, including restored earlier groups and nonmeasurement overhead. Invocation duration, measured group time and per-request latency must not be added together. These public records do not reconstruct total campaign VM allocation time.

<a id="evidence-and-replay"></a>

## Evidence and Code

| Entry | What to verify |
|---|---|
| [Runner](source/campaign_runner.py) | The dispatch, timing and campaign-control code used in the run |
| [Grader integration](source/scoring.py), [stream timing](source/stream_metrics.py) | Response/grade binding, token accounting and latency calculation |
| [Configuration](evidence/configuration.json), [requests](evidence/request-examples.json) | Fixed settings and two hashed actual payloads |
| [Run record](evidence/run.json), [events](evidence/events.jsonl) | Execution state, activation checks, source-member hashes and closure order |
| [Groups](data/groups.json), [summary](data/summary.json) | Task IDs, saved scores, timing, counters and matched comparisons |
| [Analyzer](analyze_results.py), [validator](validate_report.py) | Reaggregation and report/evidence consistency checks |

These are snapshots of the executed source, not a complete fresh-GPU installation bundle. **Complete raw answers and SSE streams remain privately archived by the author and are not redistributed here.** The public files exclude infrastructure locators and credentials. Archive and member hashes describe provenance, not independent proof of runtime behavior.

## Offline Replay

From this directory, use Python 3.10+ and its standard library. No additional dependencies, GPU, network or credentials are required:

```bash
python validate_report.py
python -m unittest discover -p "test_*.py"
```

Validation should print `REPORT_GATE=PASS`, all tests should pass, and both commands should exit with code 0. They do not start fresh inference or regrading. To regenerate the numerical summary:

```bash
python analyze_results.py --groups data/groups.json --output regenerated
```

Compare the output with the [published summary](data/summary.json). The program only reads saved grades, counts and timing; it does not execute generated answers. Commands from the parent directory are in the [overview Quick Start](../../README.md#quick-start).

<details>
<summary>Regenerating figures and report content</summary>

Add `--figure regenerated/throughput.png` to the analysis command to generate the throughput plot. This requires [Matplotlib 3.10.9](requirements-figures.txt); numerical replay does not.

After reviewing edits, `python validate_report.py --refresh --timeline` regenerates report tables, the timeline figure and the file hash inventory. Default validation is read-only. Rendered image bytes can vary with fonts or platform.

</details>

## Scope of the Conclusion

- Results describe this fixed configuration and subset; they do not prove statistical significance, distribution equivalence or formal noninferiority.
- Throughput, client latency and correct-answer delivery measure different things. They are not interchangeable and do not establish isolated GPU-kernel performance.
- The model, checkpoint and engine changed. This run does not establish that the [earlier DFlash concurrency failure](../20260905-quality/README.md) was fixed. The experiments remain separate.