# Speculative Decoding: MTP and DFlash Tests

[![vLLM](https://img.shields.io/badge/vLLM-0.28.0-0078D4.svg)](https://github.com/vllm-project/vllm/releases/tag/v0.28.0)
[![GPU](https://img.shields.io/badge/GPU-H100%20NVL-76B900.svg)](experiments/20260906-qwen38/README.md)
[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/speculative-decoding-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/speculative-decoding-ci.yml)

Use this repository to compare native MTP and DFlash 2 for Qwen3.8-27B, with weight downloads, server commands, client requests and result checks. It helps you choose which route to evaluate on your workload, rather than switching based only on output tokens per second.

On one H100 NVL, we compared Qwen3.8-27B without speculation, its native MTP, and DFlash 2 using vLLM 0.28.0. The same 64 tasks were run at concurrency 1, 4 and 8 with three seeds. DFlash 2 produced more output tokens per second than MTP in all nine paired comparisons. Scores were broadly close, but **accuracy noninferiority has not been established**.

These observations support initial selection, not production acceptance. The full-dataset phase was not executed. Earlier Qwen3.6 experiments and EAGLE3 research remain separate records and are not pooled with this run.

> Author: Xinyu Wei (魏新宇)

[English](README.md) | [中文](README-CN.md)

[Start Here](#start-here) · [Findings](#what-the-current-run-shows) · [Mechanism](#how-mtp-and-dflash-differ) · [Replay and Tests](#quick-start) · [Evidence](#evidence-and-code)

---

## Start Here

| Goal | Read |
|---|---|
| Compare speed and answer quality | [Latest measured report](experiments/20260906-qwen38/README.md) |
| Download weights, start baseline/MTP/DFlash and configure the client | [How to Run](experiments/20260906-qwen38/README.md#how-to-run) |
| Check report numbers against saved records | [Offline replay and tests](#quick-start) |
| See how the client, inference service and graders connect | [Architecture and test flow](#architecture-and-test-flow) |
| Understand the drafting difference | [How MTP and DFlash differ](#how-mtp-and-dflash-differ) |
| Inspect the first-generation DFlash concurrency failure | [Qwen3.6 complete-answer evaluation](experiments/20260905-quality/README.md) |
| Find earlier EAGLE3, training and tuning material | [Historical research notes](RESEARCH-NOTES.md) |

## What You Can Do With This Repository

| Goal | Provided assets | Practical benefit |
|---|---|---|
| Start all three inference routes | Pinned weights, complete launch commands and identical request examples | Avoid assembling MTP, DFlash and client settings from scratch |
| Select a route for further evaluation | Throughput, latency, correct counts and length stops on the same tasks | Compare speed and quality together, including cases where faster tokens do not deliver correct answers sooner |
| Check the selection evidence | Per-group records, grader integration, analysis and tests | Trace the reported numbers and design acceptance tests for your own workload |

This is a deployment reference and test evidence, not a production-validated hosted service. Preparation and scheduling for the full 27-group experiment do not yet have a standalone public entry point; see [reproduction scope](experiments/20260906-qwen38/README.md#reproduction-scope).

## What the Current Run Shows

Run ID: `qwen38-quality-20260906`. MTP7 and DFlash 2-7 in the figure both use seven draft tokens. The baseline does not use speculative decoding.

![Output throughput for three routes at concurrency 1, 4 and 8](experiments/20260906-qwen38/images/throughput.png)

*Author's measurements. Bars show medians of three runs; whiskers show the observed minimum and maximum, not confidence intervals. The same 32 code and 32 math tasks were used throughout. Throughput includes thinking tokens and uses entire-group wall time. Source: [group records](experiments/20260906-qwen38/data/groups.json).*

| Question | Observation |
|---|---|
| Was output throughput higher? | Yes. DFlash 2 exceeded MTP7 in all nine matched concurrency/seed pairs |
| Was non-decreasing accuracy proved? | No. Each dataset has 32 distinct tasks; three repeats measure variation, not 96 independent tasks |
| Were correct answers always delivered faster? | No. At concurrency 4 in the third run, DFlash 2 took longer for the same group and delivered fewer normal-stop-correct answers per second than MTP7 |
| Was the planned full dataset tested? | No. There were 1,920 completed responses out of 5,904 planned; the remaining 3,984 were not executed and are not counted as incorrect |

Scores, length stops, latency and the counterexample are in the [full report](experiments/20260906-qwen38/README.md). A throughput advantage does not replace accuracy, latency and error-rate acceptance on customer workloads.

## Architecture and Test Flow

The client and inference service share one host and communicate over loopback. Only one server mode runs at a time: baseline, MTP or DFlash. Switching modes keeps the client API unchanged. Client-side timing and grading of complete answers are separate from model inference.

```mermaid
flowchart TB
	client["Client: fixed tasks, sampling and concurrency"]
	service["vLLM 0.28.0 / one H100 NVL<br/>Qwen3.8-27B: baseline, MTP or DFlash"]
	draft["DFlash 2 draft model<br/>Loaded only in DFlash mode"]
	records["Complete answers, output tokens and client timing"]
	grading["EvalPlus / Math-Verify<br/>Grading and length-stop counts"]
	results["Per-group records and performance/quality summaries"]
	client -->|"Same request API"| service
	draft -->|"Candidates verified by target"| service
	service -->|"Streamed responses"| records
	records --> grading
	grading --> results
```

*Original test-flow diagram based on the executed [runner](experiments/20260906-qwen38/source/campaign_runner.py), [stream timing](experiments/20260906-qwen38/source/stream_metrics.py) and [grader integration](experiments/20260906-qwen38/source/scoring.py). It separates inference, client measurements and grading; the three server modes do not run simultaneously. See the [test method](experiments/20260906-qwen38/README.md#test-method) for settings and task selection.*

## How MTP and DFlash Differ

Speculative decoding uses a smaller draft model to propose candidates, then asks the target model to verify them. The target still controls which tokens enter the output.

| Aspect | MTP7 in this run | DFlash 2-7 in this run |
|---|---|---|
| Draft weights | MTP weights shipped in the Qwen3.8 checkpoint | A DFlash 2 checkpoint trained for the target |
| Candidate production | Sequential draft steps in the tested vLLM path | Block diffusion to draft a block in parallel |
| Candidates per cycle | 7 tokens | 7 tokens |
| Verification | The same Qwen3.8 target model | The same Qwen3.8 target model |

Seven is a candidate count, not network depth. One forward pass still traverses the draft model's layers. Whether MTP weights are published separately depends on the model; this run's packaging is not a universal definition of MTP.

The benefit depends on drafting and verification time per cycle, and how many tokens that cycle actually advances. More candidates need not be faster; acceptance rate is not answer accuracy. Algorithmic distribution guarantees also require a correct engine implementation and do not replace deployment quality tests.

See the [DFlash paper](https://arxiv.org/abs/2602.06036) and [pinned vLLM source](https://github.com/vllm-project/vllm/tree/2cf0a6915ce544dc493a0990f2ea38d81601128a) for mechanism context, and the [recorded configuration](experiments/20260906-qwen38/evidence/configuration.json) for this run's settings.

## Two Separate Experiments

| Experiment | Scope | Report |
|---|---|---|
| Qwen3.8 / DFlash 2 / vLLM 0.28.0 | The same 64 tasks, three seeds at each of three concurrency levels; higher throughput, quality claims limited to the subset | [Latest measurements](experiments/20260906-qwen38/README.md) |
| Qwen3.6 / first-generation DFlash / vLLM 0.21.0 | All 164 code and 500 math tasks in the primary evaluation; a separate concurrency check showed a substantial quality regression | [Complete-answer evaluation](experiments/20260905-quality/README.md) |

Targets, drafters, engines, task scope and sampling differ. Not reproducing the old failure in the newer combination does not establish that the old defect was fixed; its cause remains unresolved.

## Quick Start

Get the repository and enter this topic. Use an existing checkout directly when available:

```bash
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Deep-Learning/Speculative-Decoding
```

The latest report's checks need Python 3.10+ and its standard library, without GPU, service credentials or additional packages:

```bash
python experiments/20260906-qwen38/validate_report.py
python -m unittest discover -s experiments/20260906-qwen38 -p "test_*.py"
```

Both commands should exit with code 0, with all tests passing. They check consistency of the report, saved scores and file hashes; **they do not rerun inference or grading**. The dedicated CI runs these checks on Windows and Linux with Python 3.10 and 3.12.

For real inference, [How to Run](experiments/20260906-qwen38/README.md#how-to-run) covers weight roles, downloads, all three server modes, common parameters and client requests. This differs from offline validation, and a request smoke is not the full scored experiment. The previous report's Python 3.12 replay is documented in the [earlier experiment](experiments/20260905-quality/README.md).

## Evidence and Code

| What to inspect | Files |
|---|---|
| Scores, throughput and individual repeats | [Summary](experiments/20260906-qwen38/data/summary.json), [group records](experiments/20260906-qwen38/data/groups.json) |
| Actual settings and requests | [Configuration](experiments/20260906-qwen38/evidence/configuration.json), [request examples](experiments/20260906-qwen38/evidence/request-examples.json) |
| Completed tests and observed parameter loading | [Experiment record](experiments/20260906-qwen38/evidence/run.json) |
| Executed dispatch, timing and grader integration | [Source snapshots](experiments/20260906-qwen38/source/) |
| Numerical replay and report checks | [Analyzer](experiments/20260906-qwen38/analyze_results.py), [validator](experiments/20260906-qwen38/validate_report.py) |

The latest public bundle includes scores, timing, sample requests and executed source snapshots. Complete answers and raw streams remain in the author's archive. Public hashes detect changes within the repository; they do not independently verify withheld originals.

## Historical Research

[Historical research notes](RESEARCH-NOTES.md) retain earlier EAGLE3 validation, draft-head training, GLM/MiMo MTP parameters, capped-output speed examples and troubleshooting. They preserve earlier work, not current configuration guidance or production guarantees. The corresponding scripts, configurations, data, logs and images remain in place.

## Official Sources

- [Classical speculative decoding](https://proceedings.mlr.press/v202/leviathan23a.html)
- [DFlash paper](https://arxiv.org/abs/2602.06036) and [project source](https://github.com/z-lab/dflash)
- [vLLM 0.28.0](https://github.com/vllm-project/vllm/releases/tag/v0.28.0)
- [EvalPlus](https://github.com/evalplus/evalplus) and [MATH-500 provenance](https://github.com/openai/prm800k#math-splits)
- [EAGLE](https://github.com/SafeAILab/EAGLE) and [SpecForge](https://github.com/SafeAILab/SpecForge)