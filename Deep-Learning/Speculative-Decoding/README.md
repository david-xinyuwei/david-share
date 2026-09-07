# Speculative Decoding: MTP and DFlash 2 Measurements on Qwen3.8-27B

[![vLLM](https://img.shields.io/badge/vLLM-0.28.0-0078D4.svg)](https://github.com/vllm-project/vllm/releases/tag/v0.28.0)
[![GPU](https://img.shields.io/badge/GPU-H100%20NVL-76B900.svg?logo=nvidia&logoColor=white)](#test-method)
[![Precision](https://img.shields.io/badge/Precision-BF16-008080.svg)](#test-method)
[![Test scope](https://img.shields.io/badge/Scope-64%20tasks%20repeated-D97706.svg)](#coverage-and-unexecuted-work)
[![Evidence CI](https://github.com/david-xinyuwei/david-share/actions/workflows/speculative-decoding-ci.yml/badge.svg?branch=master)](https://github.com/david-xinyuwei/david-share/actions/workflows/speculative-decoding-ci.yml)

Use this repository to compare native MTP and DFlash 2 when deploying Qwen3.8-27B on vLLM. It provides weight downloads, all three server modes, client request settings and result checks. Use throughput, latency and answer quality together when selecting a route, rather than switching based only on output tokens per second.

On one H100 NVL, the same 32 code and 32 math tasks ran at concurrency 1, 4 and 8 with three seeds each. DFlash 2 exceeded MTP7 in output throughput across all nine matched pairs. Scores were broadly close, but at concurrency 4 in the third run, DFlash 2 answered **29/32** code tasks correctly versus **31/32** for MTP7, and took longer to finish that group. **The throughput advantage was observed; non-decreasing accuracy was not established.**

This is an author-run vLLM deployment test, not a full reproduction of the DFlash paper, and not a production acceptance result. The full-dataset phase was not executed. The earlier Qwen3.6 experiment and EAGLE3 research are kept separately later in this document and are not pooled with this run.

> Author: Xinyu Wei (魏新宇)

[English](README.md) | [中文](README-CN.md)

[Start Here](#start-here) · [Results](#throughput-and-answer-quality) · [Method](#test-method) · [How to Run](#how-to-run) · [Coverage](#coverage-and-unexecuted-work) · [Offline Replay](#offline-replay)

Run date: 2026-09-06. Run ID: `qwen38-quality-20260906`.

---

## Start Here

| Goal | Read |
|---|---|
| What this repository can do for me | [What you can do with this repository](#what-you-can-do-with-this-repository) |
| How much faster DFlash 2 is than MTP, and whether answers changed | [What the current run shows](#what-the-current-run-shows), [Throughput and answer quality](#throughput-and-answer-quality) |
| How the client, inference service and graders connect | [Architecture and test flow](#architecture-and-test-flow) |
| Download weights, start baseline/MTP/DFlash and configure the client | [How to Run](#how-to-run) |
| What was tested and what was not | [Test method](#test-method), [Coverage and unexecuted work](#coverage-and-unexecuted-work) |
| Check report numbers against saved records | [Offline replay](#offline-replay) |
| Understand the drafting difference | [How MTP and DFlash differ](#how-mtp-and-dflash-differ) |
| Inspect the first-generation DFlash concurrency failure | [Previous experiment](#previous-experiment) |
| Find earlier EAGLE3, training and serving scripts | [Earlier research assets](#research-history) |

## What You Can Do With This Repository

| Goal | Provided assets | Practical benefit |
|---|---|---|
| Start all three inference routes | Pinned weights, complete launch commands and identical request examples | Avoid assembling MTP, DFlash and client settings from scratch |
| Select a route for further evaluation | Throughput, latency, correct counts and length stops on the same tasks | Compare speed and quality together, including cases where faster tokens do not deliver correct answers sooner |
| Check the selection evidence | Per-group records, grader integration, analysis and tests | Trace the reported numbers and design acceptance tests for your own workload |

This is a deployment reference and test evidence, not a production-validated hosted service. Preparation and scheduling for the full 27-group experiment do not yet have a standalone public entry point; see [reproduction scope](#reproduction-scope).

## What the Current Run Shows

| Question | Observation |
|---|---|
| Was output throughput higher? | Yes. DFlash 2 exceeded MTP7 in all nine matched concurrency/seed pairs |
| Was non-decreasing accuracy proved? | No. Each dataset has 32 distinct tasks; three repeats measure variation, not 96 independent tasks |
| Were correct answers always delivered faster? | No. At concurrency 4 in the third run, DFlash 2 took longer for the same group and delivered fewer normal-stop-correct answers per second than MTP7 |
| Was the planned full dataset tested? | No. There were 1,920 completed responses out of 5,904 planned; the remaining 3,984 were not executed and are not counted as incorrect |

A throughput advantage does not replace accuracy, latency and error-rate acceptance on customer workloads.

## Architecture and Test Flow

The client and inference service share one host and communicate over loopback. Only one server mode runs at a time: baseline, MTP or DFlash. Switching modes keeps the client API unchanged. Client-side timing and grading of complete answers are separate from model inference.

![Test flow: client, inference service, draft model, records, grading and summaries](experiments/20260906-qwen38/images/test-flow-en.png)

*Original test-flow diagram based on the executed [runner](experiments/20260906-qwen38/source/campaign_runner.py), [stream timing](experiments/20260906-qwen38/source/stream_metrics.py) and [grader integration](experiments/20260906-qwen38/source/scoring.py); source in [test-flow-en.mmd](experiments/20260906-qwen38/images/test-flow-en.mmd). It separates inference, client measurements and grading; the three server modes do not run simultaneously.*

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

## Throughput and Answer Quality

Three routes used the same 32 HumanEval+ code tasks and 32 MATH-500 tasks at concurrency 1, 4 and 8, with three seeds each: 27 groups. **Repeating 32 tasks three times does not create 96 independent tasks per dataset.**

The baseline has no speculation; MTP7 and DFlash 2-7 each use seven draft tokens. Throughput and group wall time are separately summarized by their three-run medians. Triples in the score and length-stop tables are ordered by seed **20260906, 20260907, 20260908**. Each score is out of 32.

![Output throughput at concurrency 1, 4 and 8](experiments/20260906-qwen38/images/throughput.png)

*Figure 1. Author's measurements. Bars show medians of three runs; whiskers show observed minima and maxima, not confidence intervals. The same 64 tasks are used throughout; throughput includes thinking tokens. Source: [group records](experiments/20260906-qwen38/data/groups.json).*

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

These tables correspond to the [saved summary](experiments/20260906-qwen38/data/summary.json). Throughput is server-confirmed output tokens divided by entire-group wall time, **including thinking, incorrect and length-stopped responses**. Timing runs from the first measured request dispatch to the last request's terminal event; it excludes model download, startup, warmup and grading. This is not raw GPU decode throughput.

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

TTFT is the wait for the first output token; TPOT is the average delivery interval per output token after the first; response time runs from request dispatch to the terminal event. All three are observed at the client, and lower is better.

Each configuration first computes the P50 of each of its three runs, then takes the median of those three P50 values. **Responses are not pooled into one percentile.** Missing or undefined values are not filled with zero.

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

TTFT is timed from request dispatch to the first non-empty generated `token_ids` event; empty role or usage events do not count as the first token. TPOT is `(last_token_time - first_token_time) / (completion_tokens - 1)`, defined only when more than one token was produced and the token-ID coverage check passed.

A speculative-decoding SSE chunk can carry several tokens, so these are client-side receive metrics, not GPU kernel times. Definitions are in the [configuration](experiments/20260906-qwen38/evidence/configuration.json); observations are in the [group records](experiments/20260906-qwen38/data/groups.json).

</details>

## Test Method

The three routes keep the target model, precision, tasks, output budget and sampling fixed while switching speculative configuration. Settings come from the [saved configuration](experiments/20260906-qwen38/evidence/configuration.json); observed loading checks are in `activation` in the [run evidence](experiments/20260906-qwen38/evidence/run.json).

See [architecture and test flow](#architecture-and-test-flow) for the client, inference service and graders. Client and server share one host. Timing covers request dispatch through streamed response completion, excluding model startup and offline grading.

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

[Request examples](experiments/20260906-qwen38/evidence/request-examples.json) retain prompts, full payloads and hashes for `HumanEval/69` and `MATH-500/100` from the first baseline group. `raw_correct` records official correct verdicts; `normal_correct` also requires `finish_reason=stop`. They happen to agree in this S stage. Offline analysis uses saved grades and does not regrade answers.

</details>

## How to Run

### 1. Distinguish Target And Draft Weights

The roughly 3.8 GB file is the **DFlash 2 draft model, not the complete Qwen3.8-27B target or its MTP weights**. Do not pass it as `--model` with `method=mtp`. All three routes load the complete target checkpoint:

| Route | Target | Speculative configuration |
|---|---|---|
| Baseline | Qwen3.8-27B | Omit `--speculative-config` |
| MTP7 | Same target checkpoint, using its native MTP weights | `method="mtp"`, without a separate draft model |
| DFlash 2-7 | Same target plus the matched DFlash 2 draft | `method="dflash"`, with `model` pointing to the draft directory |

The archive records 18 target `.safetensors` files totaling 55,563,006,776 bytes (about 55.56 GB), and one draft weight file of 3,848,817,896 bytes (about 3.85 GB / 3.58 GiB). These are disk weight sizes, not total inference VRAM. **DFlash 2 is the checkpoint name; this vLLM version still uses `dflash`, not `dflash2` or `draft_model`, as the method.**

The commands use Linux x86_64, Bash and Python 3.12. The measured hardware was one H100 NVL, with a CUDA-13-compatible NVIDIA driver and enough VRAM for target, draft, KV cache and workspace. Capacity and numerical behavior on other GPUs need separate validation.

### 2. Prepare Pinned Versions

Run every command below from `Deep-Learning/Speculative-Decoding` in this repository. Create the environment only for a first installation; activate an existing verified environment with the same versions instead of rebuilding it. Downloads require tens of GB of disk space.

```bash
python3 -m venv "$HOME/.venvs/qwen38-specdec"
source "$HOME/.venvs/qwen38-specdec/bin/activate"
python -m pip install 'vllm==0.28.0' 'torch==2.13.0' 'transformers==5.16.1'
python -m pip check

export MODEL_ROOT="$HOME/models/qwen38"
hf download Qwen/Qwen3.8-27B \
	--revision 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0 \
	--local-dir "$MODEL_ROOT/target"
hf download incoai/Qwen3.8-27B-DFlash2 \
	--revision dedf8df68adfb1afeaf7b7480c0a0243108177b4 \
	--local-dir "$MODEL_ROOT/draft"
```

The directories must contain configuration, all weight shards and the target tokenizer, not a single shard alone. Key package versions come from the recorded installation; future resolution of all transitive dependencies is not guaranteed to reproduce identical environment bytes.

### 3. Set Shared Server Parameters

Run once in the server terminal. All routes use this Bash array. Keep `dflash` out of the target's local path to avoid confusing path-based model identification with its actual role. Each launch writes logs to a separate directory under `$HOME/specdec-runs/`, preserving previous results.

```bash
set -euo pipefail
export VLLM_USE_V2_MODEL_RUNNER=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export RUN_DIR="$HOME/specdec-runs/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"

COMMON=(
	--model "$MODEL_ROOT/target"
	--served-model-name Qwen/Qwen3.8-27B
	--dtype bfloat16 --tensor-parallel-size 1
	--max-model-len 32768
	--max-num-seqs 16 --max-num-batched-tokens 16384
	--gpu-memory-utilization 0.9
	--no-enable-prefix-caching --kv-cache-dtype auto
	--attention-backend FLASH_ATTN --mamba-ssm-cache-dtype float32
	--reasoning-parser qwen3 --stream-interval 1
	--generation-config vllm --seed 20260906
	--limit-mm-per-prompt '{"image":0,"video":0,"audio":0}'
	--host 127.0.0.1 --port 18080
)
```

The target and KV cache use BF16, while the Mamba SSM cache is fixed to FP32. `max-num-seqs=16` is the server scheduler limit, not a requirement to send 16 concurrent client requests. `generation-config=vllm` prevents model-directory generation defaults from replacing explicit experiment settings.

### 4. Start One Route

**Run only one route on this GPU and port at a time.** Finish a route, press `Ctrl+C` in its server terminal and use `nvidia-smi` to confirm that service has exited before starting the next one.

Baseline without speculation:

```bash
python -I -B -m vllm.entrypoints.openai.api_server "${COMMON[@]}" \
	2>&1 | tee "$RUN_DIR/baseline-server.log"
```

MTP7 using weights in the target checkpoint:

```bash
python -I -B -m vllm.entrypoints.openai.api_server "${COMMON[@]}" \
	--speculative-config '{"method":"mtp","num_speculative_tokens":7,"rejection_sample_method":"standard"}' \
	2>&1 | tee "$RUN_DIR/mtp7-server.log"
```

DFlash 2-7 with its additional draft checkpoint:

```bash
python -I -B -m vllm.entrypoints.openai.api_server "${COMMON[@]}" \
	--speculative-config "{\"method\":\"dflash\",\"model\":\"$MODEL_ROOT/draft\",\"num_speculative_tokens\":7,\"rejection_sample_method\":\"standard\"}" \
	2>&1 | tee "$RUN_DIR/dflash2_7-server.log"
```

In another terminal on the same host, check that `curl --fail http://127.0.0.1:18080/v1/models` returns `Qwen/Qwen3.8-27B`. Also inspect the startup log for the actual mode, V2 runner and precision; DFlash must load `DFlash2DraftModel`. Readiness proves loading only; send the real request below next.

### 5. Configure Client Requests And Sampling

The client always calls the same `/v1/chat/completions` endpoint and `model` name. **MTP/DFlash selection is server-side, not a client switch.** There is no Web search or RAG in this experiment. Client settings mean sampling, thinking, output budget and request concurrency. `top_k=20` controls output sampling, not the server's seven draft tokens per cycle.

| Client setting | Recorded value |
|---|---|
| Sampling | `temperature=1.0`, `top_p=0.95`, `top_k=20`, `min_p=0.0` |
| Penalties | `presence_penalty=0.0`, `repetition_penalty=1.0` |
| Thinking | `reasoning_effort="xhigh"`; template enables and preserves thinking |
| Output limit | `max_completion_tokens=16384`, including thinking |
| Stream accounting | `stream=true`, `include_usage=true`, `return_token_ids=true`, `include_reasoning=true`, `stream_interval=1` |
| Client concurrency | The measured subset uses 1, 4 and 8; base seeds 20260906, 20260907 and 20260908 |

The actual per-task seed is `int(SHA256(f"{base_seed}|{task_id}")[:8], 16) % 2147483647`, not the base seed copied to every task. [Request examples](experiments/20260906-qwen38/evidence/request-examples.json) contain the full recorded JSON. Send one directly without reconstructing its prompt or parameters.

In the client terminal, enter the same `Deep-Learning/Speculative-Decoding` directory and activate the same Python environment, then run:

```bash
set -euo pipefail
source "$HOME/.venvs/qwen38-specdec/bin/activate"
CLIENT_RUN="$HOME/specdec-runs/client-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$CLIENT_RUN"
python -c 'import json; from pathlib import Path; samples=json.loads(Path("experiments/20260906-qwen38/evidence/request-examples.json").read_text(encoding="utf-8")); print(json.dumps(samples[0]["request"], ensure_ascii=False))' \
	> "$CLIENT_RUN/request.json"
curl --fail-with-body --no-buffer --connect-timeout 10 --max-time 600 \
	http://127.0.0.1:18080/v1/chat/completions \
	-H 'Content-Type: application/json' \
	--data-binary @"$CLIENT_RUN/request.json" \
	| tee "$CLIENT_RUN/response.sse"
```

`samples[0]` is the code task; use `samples[1]` for the math task. Inspect the complete SSE for generated `token_ids`, final `usage`, `finish_reason` and `[DONE]`. A `length` finish reason means the output limit was reached, not a normally completed answer. Use the same request JSON on all three routes. The curl timeout and recording here are for request reproduction only, not the performance measurement in the tables above.

### Reproduction Scope

Commands are transcribed from the recorded installation, actual launch arguments and `server_command` in the [measurement source](experiments/20260906-qwen38/source/campaign_runner.py), with local paths replaced by environment variables. **Their scope is starting the three server modes and sending a request, not running the full performance and quality evaluation.** A new installation still needs model-loading and request checks; existing scores are not acceptance results for that environment.

Reproducing the score table additionally requires the same 64 tasks, 27 groups, frozen ordering, closed-loop concurrency, original measurement logic and EvalPlus/Math-Verify grading. The full preparation steps, task inputs and scheduling configuration required by `campaign_runner.py` are not yet packaged as a standalone public entry point, so the settings on this page cannot be passed directly to `--stage all`. Available files provide startup/request guidance and offline replay, not a standalone installer for the full 27-group experiment. Official method references: [MTP](https://github.com/vllm-project/vllm/blob/v0.28.0/docs/features/speculative_decoding/mtp.md), [pinned speculative configuration source](https://github.com/vllm-project/vllm/blob/2cf0a6915ce544dc493a0990f2ea38d81601128a/vllm/config/speculative.py).

## Coverage and Unexecuted Work

The original plan has four stages. Performance and score tables in this report use only S. Compatibility and greedy diagnostics are not pooled into the formal subset comparison.

| Stage | Completed groups | Responses | Status |
|---|---:|---:|---|
| C: compatibility | 6 | 48 | Complete |
| G: greedy diagnostics | 36 | 144 | Complete |
| S: repeated subset | 27 | 1,728 | Complete |
| F: full datasets | 0 | 0 | Not run |

Totals are **69/81 groups and 1,920/5,904 responses**. The remaining 12 groups and 3,984 responses were not executed: neither removed from the plan nor marked incorrect. These results cover the completed work, not a pass for the entire plan.

F would run all three routes at concurrency 1 and 8 over all 164 HumanEval+ and 500 MATH-500 tasks, once per task, with seed 20260906. This stage was not executed. The measured subset is not a full-dataset score; the [coverage record](experiments/20260906-qwen38/evidence/run.json) preserves the original plan and unexecuted items.

### Measured Duration by Stage

| Stage | Sum of group wall times (s) |
|---|---:|
| Compatibility (C) | 928.51 |
| Greedy diagnostics (G) | 387.09 |
| Repeated subset (S) | 27,800.41 |
| Full datasets (F) | 0, not run |

These sum measured group times from request dispatch to response completion, excluding model downloads, server startup, warmup and grading. Values are rounded to two decimals; exact values remain in [run evidence](experiments/20260906-qwen38/evidence/run.json). Complete describes execution, not perfect correctness.

<a id="previous-experiment"></a>

## Previous Experiment: Qwen3.6-27B and First-Generation DFlash (2026-09-05)

The previous run used Qwen3.6-27B, the first-generation DFlash draft model and vLLM 0.21.0 on the same H100 NVL, and completed all 164 HumanEval+ and 500 MATH-500 tasks with complete answers. **DFlash15 was faster per request and its primary scores were close to the baseline, but at concurrency 4 and 8 answer quality on the same 32 code and 32 math tasks regressed substantially.** The cause has not been identified, and no fixed configuration has been retested.

The two runs differ in target model, draft model, engine, task scope and sampling. Not reproducing the old failure in the newer combination does not establish that the old defect was fixed.

### Primary Evaluation: Full Datasets, Once per Task

Code had to pass both the base and extended official EvalPlus tests; math was graded by the pinned official Math-Verify script. Length-stopped responses stay in the denominator.

| Route | HumanEval+ | MATH-500 | Code base tests | Math length stops |
|---|---:|---:|---:|---:|
| Baseline | 152/164 (92.68%) | 489/500 (97.80%) | 159/164 | 4 |
| MTP5 | 155/164 (94.51%) | 494/500 (98.80%) | 162/164 | 2 |
| DFlash15 | 153/164 (93.29%) | 490/500 (98.00%) | 160/164 | 3 |

Median code request times for Baseline, MTP5 and DFlash15 were 4.393, 1.175 and 0.660 seconds; math 15.666, 4.542 and 2.980 seconds. Median code output rates were 53.61, 196.01 and 367.52 tok/s; math 54.05, 187.60 and 281.77 tok/s. Timing includes prefill and same-host client overhead and excludes server startup. Computing MTP5 time divided by DFlash15 time per task and then taking the median gives 1.861 for code and 1.498 for math. Five versus fifteen draft tokens is not an equal compute budget, nor a tuned best configuration per route.

![Previous run: complete-answer request time](experiments/20260905-quality/analysis/figures/primary-latency.png)

*Author's measurements, run dflash-quality-20260905, 164 code and 500 math tasks per route, once each. Values come from the [per-task replay summary](experiments/20260905-quality/analysis/summary.json). Total request time over all answers, not isolated decode-kernel time.*

### Concurrency Quality Did Not Pass

Each level used the first 32 code and first 32 math tasks of the frozen manifest, once each. Concurrency is the number of in-flight requests from the same-host client, not an arrival rate.

| Route | Concurrency | HumanEval+ | Math subset | Length stops (code/math) |
|---|---:|---:|---:|---:|
| Baseline | 1 | 32/32 | 32/32 | 0/0 |
| Baseline | 4 | 32/32 | 30/32 | 0/0 |
| Baseline | 8 | 32/32 | 31/32 | 0/0 |
| MTP5 | 1 | 32/32 | 31/32 | 0/0 |
| MTP5 | 4 | 32/32 | 31/32 | 0/0 |
| MTP5 | 8 | 32/32 | 32/32 | 0/0 |
| DFlash15 | 1 | 32/32 | 31/32 | 0/1 |
| DFlash15 | 4 | 11/32 | 13/32 | 8/17 |
| DFlash15 | 8 | 10/32 | 12/32 | 13/20 |

![Previous run: correct answers under concurrency on the same tasks](experiments/20260905-quality/analysis/figures/concurrency-quality.png)

*Author's measurements, the same 32+32 tasks, once per level. Raw responses and official grades are in the [results directory](experiments/20260905-quality/results/); the summary is in the [analysis output](experiments/20260905-quality/analysis/summary.json). The anomaly is bound to that tested combination; the curves are not a root-cause proof.*

HumanEval/2 is a concrete example: the normalized request hash is identical at all three levels. [Concurrency 1](experiments/20260905-quality/results/dflash15/concurrency-1/repeat-0/HumanEval_2.json) returned a correct function; [concurrency 4](experiments/20260905-quality/results/dflash15/concurrency-4/repeat-0/HumanEval_2.json) returned an empty definition and a JSON fragment; [concurrency 8](experiments/20260905-quality/results/dflash15/concurrency-8/repeat-0/HumanEval_2.json) produced unrelated function names and repeated text until the 4,096-token limit. That DFlash15 configuration cannot carry concurrent traffic on the strength of single-request results, and the evidence does not attribute the cause to a vLLM component, floating-point error, DFlash theory, the H100 or the cloud platform.

Each primary route has 1,012 responses (664 primary, 48 same-seed repeats, 48 streaming, 192 concurrency, 48 random sampling, 12 synthetic retrieval); with 64 matched-window DFlash5 responses, the total is **3,100 responses across 25 route/scenario combinations**. DFlash5 scored 32/32 on both code and math; its concurrency was not tested.

### Previous Run: Fixed Method

| Item | Recorded value |
|---|---|
| GPU | One NVIDIA H100 NVL, 95,830 MiB; driver 610.57.04 |
| Target | `Qwen/Qwen3.6-27B` @ `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`, BF16 |
| Draft model | `z-lab/Qwen3.6-27B-DFlash` @ `0919688658996800f86b895034249700e9481106` |
| Generation environment | vLLM 0.21.0, PyTorch 2.11.0, transformers 4.57.6 |
| Graders | EvalPlus @ `26d6d00bb1fd0fa37f39c99d5290da67891d1c5e`; Math-Verify @ `ba3d3aaff23b3f4cac7a14672b4f6e293d97c98b` |
| Datasets | HumanEval+ v0.1.10; MATH-500 @ `6e4ed1a2a79af7d8630a6b768ec859cb5af4d3be` |
| Primary sampling | temperature 0, top_p 1, top_k -1, seed 20260905; `enable_thinking=false` |
| Server settings | max_model_len 40960, max_num_seqs 16, max_num_batched_tokens 8192, GPU memory utilization 0.9, prefix caching disabled |
| Output budget | Code 4096, math 8192 |

File hashes for the model, configuration and tokenizer, plus package versions, are in [inputs.json](experiments/20260905-quality/metadata/inputs.json). The [public protocol](experiments/20260905-quality/src/experiment.json) only removes private resource-management objects; the [projection record](experiments/20260905-quality/metadata/protocol-public-projection.json) records hashes before and after. Code grading ran in an offline, unprivileged Docker container.

<details>
<summary>Rerun the previous generation in a fresh directory (requires an H100 NVL and Docker)</summary>

Requires Linux, Python 3.12, a compatible H100 NVL environment and disk space for both weight snapshots and dependencies. The grading container runs as UID/GID 1000 and the host must allow `sudo -n` Docker calls. Start from `experiments/20260905-quality`, create a new run directory and do not overwrite the provided evidence.

```bash
set -euo pipefail
SOURCE="$PWD"
export DFLASH_RUN_ROOT="$(mktemp -d "$HOME/quality-replay-XXXXXXXX")"
export DFLASH_CACHE_ROOT="$DFLASH_RUN_ROOT/cache"
export DFLASH_TARGET_PATH="$DFLASH_CACHE_ROOT/target"
[[ "${DFLASH_TARGET_PATH,,}" != *dflash* ]]
mkdir -p "$DFLASH_RUN_ROOT"/{src,data,metadata,logs,results,state,upstream}
cp src/quality_runner.py src/prepare_data.py src/experiment.json "$DFLASH_RUN_ROOT/src/"
cp data/math500.jsonl data/humaneval_plus.jsonl "$DFLASH_RUN_ROOT/data/"
python3.12 -m venv "$DFLASH_CACHE_ROOT/venv"
PYTHON="$DFLASH_CACHE_ROOT/venv/bin/python"
"$PYTHON" -m pip install -r "$SOURCE/metadata/requirements-frozen.txt"
"$DFLASH_CACHE_ROOT/venv/bin/hf" download Qwen/Qwen3.6-27B --revision 6a9e13bd6fc8f0983b9b99948120bc37f49c13e9 --local-dir "$DFLASH_CACHE_ROOT/target"
"$DFLASH_CACHE_ROOT/venv/bin/hf" download z-lab/Qwen3.6-27B-DFlash --revision 0919688658996800f86b895034249700e9481106 --local-dir "$DFLASH_CACHE_ROOT/draft"
curl --fail --location 'https://raw.githubusercontent.com/huggingface/Math-Verify/ba3d3aaff23b3f4cac7a14672b4f6e293d97c98b/evaluate_model_outputs.py' -o "$DFLASH_RUN_ROOT/upstream/math-verify-evaluate.py"
curl --fail --location 'https://github.com/evalplus/mbppplus_release/releases/download/v0.2.0/MbppPlus.jsonl.gz' -o "$DFLASH_RUN_ROOT/upstream/mbpp-plus-v0.2.0.jsonl.gz"
gzip -dc "$DFLASH_RUN_ROOT/upstream/mbpp-plus-v0.2.0.jsonl.gz" > "$DFLASH_RUN_ROOT/upstream/mbpp-plus-v0.2.0.jsonl"
HUMANEVAL_OVERRIDE_PATH="$DFLASH_RUN_ROOT/data/humaneval_plus.jsonl" "$PYTHON" src/prepare_data.py --root "$DFLASH_RUN_ROOT" --cache "$DFLASH_CACHE_ROOT"
sudo -n docker build -f src/Dockerfile.eval -t dflash-quality-eval:20260905 .
"$PYTHON" "$DFLASH_RUN_ROOT/src/quality_runner.py" --phase canary
"$PYTHON" "$DFLASH_RUN_ROOT/src/quality_runner.py" --phase full
"$PYTHON" "$DFLASH_RUN_ROOT/src/quality_runner.py" --phase full --route dflash5
printf '{"phase":"COMPLETE","exit_code":0}\n' > "$DFLASH_RUN_ROOT/state/campaign.json"
"$PYTHON" "$SOURCE/src/analyze_results.py" --root "$DFLASH_RUN_ROOT" --output "$DFLASH_RUN_ROOT/analysis/summary.json" --matrix
```

The generation CLI stops only its own model server and does not release the host. Compare against the [grader dependency versions](experiments/20260905-quality/metadata/evaluator-requirements-frozen.txt) and the [original image ID](experiments/20260905-quality/metadata/evaluator-image-id.txt) when rerunning; even with pinned grader commits, Docker base tags and system packages can change. vLLM 0.21.0 accepts `standard` but not `strict`, and a target path containing `dflash` can trigger a wrong method inference.

</details>

<a id="research-history"></a>

## Earlier Research Assets (first half of 2026)

The following work predates both formal evaluations and used different models, engine versions and methods. It documents where the scripts, configurations and data came from; it is not current parameter guidance or a quality guarantee.

| Phase | What was done | Recorded result |
|---|---|---|
| Official EAGLE3 model validation | Served the official Llama-3.1-8B EAGLE3 draft head on vLLM; 20 runs of 512 tokens | 441.7 tok/s average versus 165.7 tok/s baseline, about 2.67x |
| Self-trained EAGLE3 draft head | Trained with SpecForge on one H100 in about 45 minutes | 1.30x on code generation; about 1.00x on technical Q&A and math; 0.84x on creative writing |
| H100 three-route speed sample (2026-06-28) | Qwen3.6-27B: vLLM native MTP (5 candidates), vLLM DFlash (15 candidates), llama.cpp MTP Q4_K_XL; median of 3 runs per task type | Coding median TPS 146.7, 191.7 and 107.3 respectively |

The 2026-06-28 sample used **capped outputs**: all 18 formal vLLM records ended with `finish_reason="length"`, no answers were graded and TTFT was not measured. Candidate counts differ, so it does not rank the algorithms. Complete-answer quality evaluation began with the previous experiment above.

| Asset | Contents |
|---|---|
| [`config/`](config/) | EAGLE3 training/deployment configuration `eagle3_llama31_8b.yaml` and the Llama-3.1-8B EAGLE3 draft-head architecture `llama3-8B-eagle3.json` |
| [`scripts/`](scripts/) | EAGLE3 server launch and training scripts, training-data preparation; Qwen3.6 vLLM MTP/DFlash and llama.cpp MTP launch scripts; the three-route benchmark client and orchestrator |
| [`data/`](data/) | Raw 2026-06-28 benchmark results `h100_vllm_native_mtp.json`, `h100_vllm_dflash.json` and `h100_llamacpp_mtp_q4kxl.json` |
| [`logs/`](logs/) | EAGLE3 server startup and training sample logs, plus the three-route server startup logs |
| [`images/`](images/) | EAGLE3 architecture, training comparison and EAGLE/MTP parameter illustrations |
| [`test_performance.py`](test_performance.py), [`requirements.txt`](requirements.txt) | The early performance test script and its dependencies |

## Evidence and Code

| Entry | What to verify |
|---|---|
| [Runner](experiments/20260906-qwen38/source/campaign_runner.py) | The dispatch, timing and campaign-control code used in the run |
| [Grader integration](experiments/20260906-qwen38/source/scoring.py), [stream timing](experiments/20260906-qwen38/source/stream_metrics.py) | Response/grade binding, token accounting and latency calculation |
| [Configuration](experiments/20260906-qwen38/evidence/configuration.json), [requests](experiments/20260906-qwen38/evidence/request-examples.json) | Fixed settings and two hashed actual payloads |
| [Experiment record](experiments/20260906-qwen38/evidence/run.json) | Coverage, activation checks, measured durations and source-member hashes |
| [Groups](experiments/20260906-qwen38/data/groups.json), [summary](experiments/20260906-qwen38/data/summary.json) | Task IDs, saved scores, timing, counters and matched comparisons |
| [Analyzer](experiments/20260906-qwen38/analyze_results.py), [validator](experiments/20260906-qwen38/validate_report.py), [tests](experiments/20260906-qwen38/test_report.py) | Reaggregation and checks that this document's tables, links, badges and evidence agree |
| [Previous analysis](experiments/20260905-quality/analysis/), [previous results](experiments/20260905-quality/results/), [previous source](experiments/20260905-quality/src/) | 2026-09-05 per-task comparisons, raw responses, official grades and analysis code |

These are snapshots of the executed source, not a complete fresh-GPU installation bundle. **Complete raw answers and SSE streams remain privately archived by the author and are not redistributed here.** The public files exclude infrastructure locators and credentials. Archive and member hashes describe provenance, not independent proof of runtime behavior.

## Offline Replay

Run from `Deep-Learning/Speculative-Decoding` with Python 3.10+ and its standard library. No additional dependencies, GPU, network or credentials are required:

```bash
python experiments/20260906-qwen38/validate_report.py
python -m unittest discover -s experiments/20260906-qwen38 -p "test_*.py"
```

Validation should print `REPORT_GATE=PASS`, all tests should pass, and both commands should exit with code 0. They check that this document's tables, saved scores and file hashes agree; they do not start fresh inference or regrading. The dedicated CI runs these checks on Windows and Linux with Python 3.10 and 3.12.

To independently check summary values from the per-group records:

```bash
python experiments/20260906-qwen38/analyze_results.py --groups experiments/20260906-qwen38/data/groups.json --output experiments/20260906-qwen38/regenerated
```

Compare `summary.json` in the output directory with the [published summary](experiments/20260906-qwen38/data/summary.json). The program only reads saved grades, counts and timing; it does not execute generated answers.

Replaying the previous experiment requires Python 3.12. It checks all 3,100 requests, the frozen task set, task/repeat counts and grade binding; missing or mismatched items fail instead of shrinking the denominator:

```bash
python experiments/20260905-quality/src/analyze_results.py --root experiments/20260905-quality --output out/20260905-replayed.json --matrix
```

## Scope of the Conclusion

- Results describe this fixed configuration and subset; they do not prove statistical significance, distribution equivalence or formal noninferiority.
- Throughput, client latency and correct-answer delivery measure different things. They are not interchangeable and do not establish isolated GPU-kernel performance.
- The model, checkpoint and engine changed. This run does not establish that the previous DFlash concurrency failure was fixed. The experiments remain separate.

## Official Sources

- [Classical speculative decoding](https://proceedings.mlr.press/v202/leviathan23a.html)
- [DFlash paper](https://arxiv.org/abs/2602.06036) and [project source](https://github.com/z-lab/dflash)
- [vLLM 0.28.0](https://github.com/vllm-project/vllm/releases/tag/v0.28.0)
- [EvalPlus](https://github.com/evalplus/evalplus) and [MATH-500 provenance](https://github.com/openai/prm800k#math-splits)
- [EAGLE](https://github.com/SafeAILab/EAGLE) and [SpecForge](https://github.com/SafeAILab/SpecForge)
