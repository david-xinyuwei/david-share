<a id="english"></a>

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

English | [中文](#chinese)

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
| [`images/`](images/) | EAGLE3 architecture, training comparison and EAGLE/MTP parameter illustrations, plus the Chinese result figures used by the Chinese section |
| [`tools/make_readme_figures.py`](tools/make_readme_figures.py) | Regenerates the Chinese section's result figures from both experiments' published summaries; requires Matplotlib and a CJK font |
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

---

<a id="chinese"></a>

# 推测解码：Qwen3.8-27B 上的 MTP 与 DFlash 2 实测


这个仓库帮助你在 vLLM 上部署 Qwen3.8-27B 时比较模型自带的 MTP 和 DFlash 2，并提供权重下载、三种服务启动、客户端请求配置和结果核对方法。选型同时看吞吐、延迟和答案质量，不能只凭每秒输出多少 token 决定是否切换。

在单张 H100 NVL 上，同一批 32 道代码题和 32 道数学题在并发 1、4、8 下各跑三次。九组配对中，DFlash 2 的输出吞吐均高于 MTP7。得分总体接近，但并发 4 的第三次运行里，DFlash 2 的代码题答对 **29/32**，MTP7 为 **31/32**，而且 DFlash 2 做完这一组题更慢。**吞吐优势已经测到，准确率不下降尚未得到证明。**

这是作者在 vLLM 上的部署实测，不是 DFlash 论文的完整复现，也不能直接作为生产验收结论。完整题集阶段未执行；更早的 Qwen3.6 实验和 EAGLE3 研究独立保留在本文后半部分，不与本次数字混算。

> 作者：魏新宇（Xinyu Wei）

[English](#english) | 中文

[从这里开始](#从这里开始) · [结果](#吞吐与答案质量) · [方法](#测试方法) · [启动与调用](#how-to-run-cn) · [覆盖范围](#测试覆盖与未执行项) · [离线复算](#离线复算)

实验日期：2026-09-06。运行标识：`qwen38-quality-20260906`。

---

## 从这里开始

| 你想了解什么 | 入口 |
|---|---|
| 这个仓库能帮我做什么 | [你能用它做什么](#你能用它做什么) |
| DFlash 2 比 MTP 快多少，答案有没有变差 | [本次实测说明了什么](#本次实测说明了什么)、[吞吐与答案质量](#吞吐与答案质量) |
| 客户端、推理服务和评分怎样连接 | [架构与测试流程](#架构与测试流程) |
| 下载权重，启动基线、MTP 或 DFlash，设置客户端 | [启动与调用](#how-to-run-cn) |
| 测了什么、没测什么 | [测试方法](#测试方法)、[测试覆盖与未执行项](#测试覆盖与未执行项) |
| 核对报告数字和已保存记录 | [离线复算](#离线复算) |
| 理解两种起草方式的区别 | [MTP 和 DFlash 差在哪里](#mtp-和-dflash-差在哪里) |
| 回看首代 DFlash 的并发异常 | [上一轮实验](#previous-experiment-cn) |
| 查早期 EAGLE3、训练和服务脚本 | [早期研究资产](#research-history-cn) |

## 你能用它做什么

| 目标 | 仓库提供什么 | 对你的帮助 |
|---|---|---|
| 启动三条推理路线 | 固定权重版本、完整启动命令和相同请求样例 | 不必从零拼装 MTP、DFlash 与客户端参数 |
| 判断哪条路线值得验证 | 同一批题目的吞吐、延迟、答对数和截断记录 | 同时比较速度与答案质量，识别“token 更快、正确答案反而交付更慢”的情况 |
| 核对选型依据 | 逐组数据、评分接入源码、分析程序和测试 | 能检查报告数字从何而来，再为自己的业务设计验收 |

这里提供的是部署参考和测试依据，不是经过生产验收的托管服务。完整 27 组实验的准备与调度尚未提供独立运行入口，边界见[复现范围](#复现范围)。

## 本次实测说明了什么

| 问题 | 实测回答 |
|---|---|
| 输出吞吐更高吗 | 是。三档并发、三个随机种子的九组配对中，DFlash 2 都高于 MTP7 |
| 准确率不下降得到证明了吗 | 没有。每类只有 32 道不同题目，三次重复用于观察波动，不能当成 96 道独立题 |
| 正确答案也一定更快交付吗 | 不一定。并发 4 的第三次运行中，DFlash 2 做完同一组题更慢，正常结束且答对的答案交付速率也低于 MTP7 |
| 原定全量题集都测了吗 | 没有。已完成 1,920 份响应，原计划 5,904 份；其余 3,984 份未执行，不计作答错 |

吞吐优势不能替代客户负载上的准确率、延迟和异常率验收。

## 架构与测试流程

客户端与推理服务运行在同一台机器上，通过回环地址通信。服务端每次只启动基线、MTP 或 DFlash 中的一种模式；切换模式不改变客户端 API。客户端记录请求耗时，评分程序检查生成的完整答案。

![测试流程：客户端、推理服务、草稿模型、记录、评分与汇总](experiments/20260906-qwen38/images/test-flow-cn.png)

*原创测试流程图，依据本次[执行程序](experiments/20260906-qwen38/source/campaign_runner.py)、[流式计时](experiments/20260906-qwen38/source/stream_metrics.py)与[评分接入](experiments/20260906-qwen38/source/scoring.py)绘制；图源为 [test-flow-cn.mmd](experiments/20260906-qwen38/images/test-flow-cn.mmd)。图中区分推理、客户端测量和评分；三种模式并非同时运行。*

## MTP 和 DFlash 差在哪里

推测解码先由草稿模型（draft model）提出候选，再由目标模型验证。目标模型仍决定哪些 token 能进入输出。

| 比较项 | 本次 MTP7 | 本次 DFlash 2-7 |
|---|---|---|
| 起草所用权重 | Qwen3.8 模型文件自带的 MTP 权重 | 与目标模型配套的 DFlash 2 权重 |
| 候选怎样生成 | 在本次 vLLM 路径中逐步起草 | 通过块扩散（block diffusion）并行生成一组候选 |
| 每轮候选数量 | 7 个 token | 7 个 token |
| 谁做最终验证 | 同一个 Qwen3.8 目标模型 | 同一个 Qwen3.8 目标模型 |

这里的“7”是候选数量，不是网络层数。一次前向计算也不表示网络只有一层；它仍会经过草稿模型的各层。MTP 权重是否单独发布，随具体模型而异，不能把本次的打包方式当成 MTP 的统一定义。

推测解码的收益取决于两件事：每轮起草与验证花了多久，以及这一轮实际推进了多少个 token。候选越多，不一定越快；接受率也不是答案准确率。采样算法的分布保证，还需要正确的引擎实现，不能替代部署后的质量测试。

机制资料见 [DFlash 论文](https://arxiv.org/abs/2602.06036)和 [vLLM 固定版本源码](https://github.com/vllm-project/vllm/tree/2cf0a6915ce544dc493a0990f2ea38d81601128a)；本次参数见[实验配置](experiments/20260906-qwen38/evidence/configuration.json)。

## 吞吐与答案质量

使用 32 道 HumanEval+ 代码题和 32 道 MATH-500 数学题，三条路线在并发 1、4、8 下各跑三次，共 27 组。每组都是同一批题，**每类 32 题重复三次，不是 96 道独立题**。

基线不开推测解码；MTP7 和 DFlash 2-7 都起草 7 个候选 token。下表的吞吐和整组耗时分别取三次运行的中位数。得分和截断列的三个数，依次对应随机种子 **20260906、20260907、20260908**；每个得分的分母都是 32。

![三种路线在并发 1、4、8 下的输出吞吐](images/throughput-cn.png)

*图 1：作者实测。柱形表示三次运行的中位数，误差线表示最小值和最大值，不是置信区间；同一批 64 题，吞吐包含思考过程中的 token。数据来自[数值汇总](experiments/20260906-qwen38/data/summary.json)，由[绘图脚本](tools/make_readme_figures.py)生成。*

<!-- BEGIN RESULT_TABLE_CN -->
### 吞吐与整组耗时

| 并发 | 路线 | 吞吐（tok/s） | 整组耗时（秒） |
| --- | --- | --- | --- |
| 1 | 基线 | 53.40 | 3458.61 |
| 1 | MTP7 | 113.34 | 1591.09 |
| 1 | DFlash 2-7 | 150.51 | 1149.41 |
| 4 | 基线 | 190.08 | 1037.22 |
| 4 | MTP7 | 382.85 | 470.35 |
| 4 | DFlash 2-7 | 451.74 | 377.79 |
| 8 | 基线 | 287.72 | 577.44 |
| 8 | MTP7 | 565.24 | 308.08 |
| 8 | DFlash 2-7 | 741.07 | 249.68 |

### 代码与数学得分

| 并发 | 路线 | 代码答对数 /32 | 数学答对数 /32 |
| --- | --- | --- | --- |
| 1 | 基线 | 29、31、30 | 30、30、30 |
| 1 | MTP7 | 30、31、31 | 30、28、31 |
| 1 | DFlash 2-7 | 30、31、30 | 29、32、30 |
| 4 | 基线 | 31、31、31 | 30、31、30 |
| 4 | MTP7 | 30、30、31 | 29、29、29 |
| 4 | DFlash 2-7 | 31、31、29 | 31、31、30 |
| 8 | 基线 | 31、31、31 | 30、29、30 |
| 8 | MTP7 | 31、31、30 | 29、29、30 |
| 8 | DFlash 2-7 | 31、31、30 | 30、31、30 |

本次所有被评分器判对的回答都正常结束，因此“答对数”和“正常结束且答对数”相同，不重复列两遍。两项原始字段均保留在数据文件中。

<details>
<summary>查看三次运行的截断情况</summary>

| 并发 | 路线 | 代码截断数 | 数学截断数 |
| --- | --- | --- | --- |
| 1 | 基线 | 1、1、2 | 2、1、2 |
| 1 | MTP7 | 2、1、1 | 1、2、1 |
| 1 | DFlash 2-7 | 2、1、2 | 2、0、1 |
| 4 | 基线 | 1、1、1 | 1、0、2 |
| 4 | MTP7 | 2、2、1 | 2、1、2 |
| 4 | DFlash 2-7 | 1、1、3 | 1、1、1 |
| 8 | 基线 | 1、1、1 | 2、2、2 |
| 8 | MTP7 | 1、1、2 | 2、1、1 |
| 8 | DFlash 2-7 | 1、1、2 | 2、1、2 |

达到输出上限的回答仍保留在每次 32 题的分母中。

</details>
<!-- END RESULT_TABLE_CN -->

以上各表对应[数值汇总](experiments/20260906-qwen38/data/summary.json)。吞吐按“服务端确认的输出 token 总数 ÷ 整组耗时”计算，**包含思考过程、错答和截断回答中的 token**。计时从首个测量请求派发，到最后一个请求的终止事件接收完成；不含模型下载、启动、预热和评分。这不是 GPU 纯解码吞吐。

### 为什么还要看正确答案的交付速度

<!-- BEGIN COUNTEREXAMPLE_CN -->
并发 4 的第三次运行（seed 20260908）出现了一个例外：**DFlash 2 输出 token 更快，但做完同一组题反而更慢。** 下表只统计正常结束且答对的回答，耗时取自这一次运行，不是三次运行的中位数。

| 路线 | 整组耗时（秒） | 代码答对数 /32 | 数学答对数 /32 |
| --- | --- | --- | --- |
| MTP7 | 450.87 | 31 | 29 |
| DFlash 2-7 | 484.07 | 29 | 30 |

DFlash 2 有 3 份代码回答达到输出上限。用“正常结束且答对数 ÷ 整组耗时”衡量正确答案的交付速度，DFlash 2 与 MTP7 的比值为：代码 **0.8713**，数学 **0.9635**。两者都小于 1。这说明 token 吞吐优势不能直接当成正确答案的交付优势；这次差异的原因尚未定位。
<!-- END COUNTEREXAMPLE_CN -->

## 客户端延迟

TTFT 是等待首个输出 token 的时间；TPOT 是首个 token 之后，平均每个输出 token 的交付间隔；回答耗时是从请求派发到接收终止事件的时间。三项都从客户端观察，数值越低越好。

每个配置先分别计算三次运行的 P50，再取三个 P50 的中位数，**不是把所有响应合并后求一次分位数**。缺失或无定义的值不补零。

<!-- BEGIN LATENCY_TABLE_CN -->
### 首 token 等待（TTFT，ms）

| 并发 | 基线 | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 82.727 | 75.127 | 80.286 |
| 4 | 104.008 | 110.259 | 115.994 |
| 8 | 106.598 | 124.699 | 124.781 |

### token 交付间隔（TPOT，ms/token）

| 并发 | 基线 | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 18.567 | 8.011 | 5.875 |
| 4 | 20.104 | 8.549 | 6.739 |
| 8 | 20.845 | 10.041 | 7.892 |

### 单次回答耗时（秒）

| 并发 | 基线 | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 16.359 | 6.236 | 6.185 |
| 4 | 19.035 | 8.661 | 5.237 |
| 8 | 18.457 | 9.915 | 7.742 |

每个配置、每项指标均有 192 份有效响应记录，缺失 0 份。这是重复运行的观测数，不是独立题目数。
<!-- END LATENCY_TABLE_CN -->

<details>
<summary>查看延迟的精确定义</summary>

TTFT 从派发请求计时，到首个非空生成 `token_ids` 事件为止；空的角色事件或 usage 事件不算首 token。TPOT 按 `(last_token_time - first_token_time) / (completion_tokens - 1)` 计算，仅在输出多于一个 token、且 token-ID 覆盖校验通过时有效。

一个推测解码 SSE 块可以包含多个 token，所以这些是客户端接收侧指标，不是 GPU kernel 的执行时间。定义见[配置](experiments/20260906-qwen38/evidence/configuration.json)，观测值见[逐组记录](experiments/20260906-qwen38/data/groups.json)。

</details>

## 测试方法

三条路线固定目标模型、数值精度、题目、输出预算和采样设置，只切换推测解码配置。参数来自当时保存的[配置](experiments/20260906-qwen38/evidence/configuration.json)，实际加载检查记录在[运行证据](experiments/20260906-qwen38/evidence/run.json)的 `activation` 中。

客户端、推理服务与评分程序的关系见[架构与测试流程](#架构与测试流程)。本次客户端与服务端同机，计时包含请求派发与流式响应接收，不把模型启动或离线评分时间算作推理性能。

| 项目 | 本次设置 |
|---|---|
| 硬件 | 单张 H100 NVL，张量并行度为 1 |
| 目标模型 | Qwen3.8-27B，BF16 |
| MTP | 目标模型文件自带的多 token 预测权重，未另行训练或转换 |
| DFlash 2 | incoai 发布的 Qwen3.8-27B-DFlash2，BF16 |
| 推理引擎 | vLLM 0.28.0，实际加载 Model Runner V2 |
| 候选数量 | 基线为 0；MTP7 和 DFlash 2-7 均为 7 |
| 输出预算 | 每题最多 16,384 个 token，包含思考过程 |
| 思考设置 | 开启并保留思考过程（thinking），`reasoning_effort="xhigh"` |
| 采样 | temperature 为 1.0，top_p 为 0.95，top_k 为 20 |
| 配对方式 | 并发 1、4、8；随机种子为 20260906、20260907、20260908 |

每类 32 个题目 ID 按预先固定的 SHA-256 排序规则选取，不参考回答和分数。三条路线使用相同的逐题随机种子，但这不代表每一步随机抽样完全对齐。代码题由 EvalPlus 官方工具评分，数学题由 Math-Verify 官方工具评分。

<details>
<summary>查看固定版本、完整参数与请求样例</summary>

以下链接固定到实际使用的版本，不指向模型仓库当前最新版：

| 对象 | 版本记录 |
|---|---|
| 目标模型 | [Qwen3.8-27B 固定版本权重](https://huggingface.co/Qwen/Qwen3.8-27B/tree/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0) |
| DFlash 2 | [Qwen3.8-27B-DFlash2 固定版本权重](https://huggingface.co/incoai/Qwen3.8-27B-DFlash2/tree/dedf8df68adfb1afeaf7b7480c0a0243108177b4)，架构为 `DFlash2DraftModel` |
| vLLM | [0.28.0 固定源码](https://github.com/vllm-project/vllm/tree/2cf0a6915ce544dc493a0990f2ea38d81601128a) |
| EvalPlus | [固定源码](https://github.com/evalplus/evalplus/tree/26d6d00bb1fd0fa37f39c99d5290da67891d1c5e)，使用官方 sanitize/evaluate CLI |
| Math-Verify | [固定源码](https://github.com/huggingface/Math-Verify/tree/ba3d3aaff23b3f4cac7a14672b4f6e293d97c98b)，使用官方 `evaluate_model_outputs.py` |

其余参数为 `min_p=0.0`、`presence_penalty=0.0`、`repetition_penalty=1.0`。模板同时设置 `enable_thinking=true` 和 `preserve_thinking=true`；调度上限为 `max_model_len=32768`、`max_num_seqs=16`、`max_num_batched_tokens=16384`。

客户端按固定顺序发送请求：一个请求完成后再补发下一个，保持指定并发数。相同客户端并发不代表 GPU 每批处理的请求数和序列长度相同。记录中的路线标识分别为 `baseline`、`mtp7`、`dflash2_7`；配置中的基础随机种子为 20260906。

[请求样例](experiments/20260906-qwen38/evidence/request-examples.json)保存了第一组基线运行中 `HumanEval/69` 和 `MATH-500/100` 的提示词、完整参数及哈希。`raw_correct` 记录评分器判对数，`normal_correct` 还要求 `finish_reason=stop`；二者在本次 S 阶段恰好一致。离线分析使用已保存的评分，不重新判分。

</details>

<a id="how-to-run-cn"></a>

## 启动与调用

### 1. 先分清目标模型和草稿模型权重

约 3.8 GB 的文件是 **DFlash 2 的草稿模型（draft model），不是完整的 Qwen3.8-27B，也不是它的 MTP 权重**。不能把该文件作为 `--model` 再指定 `method=mtp`。三条路线都必须加载完整目标模型权重：

| 路线 | 目标模型 | 推测配置 |
|---|---|---|
| 基线 | Qwen3.8-27B | 不传 `--speculative-config` |
| MTP7 | 同一目标模型，使用其自带 MTP 权重 | `method="mtp"`，不另传草稿模型 |
| DFlash 2-7 | 同一目标模型，另加载 DFlash 2 草稿模型 | `method="dflash"`，`model` 指向草稿模型目录 |

本次记录的目标 `.safetensors` 共 18 个、55,563,006,776 字节（约 55.56 GB）；草稿模型权重为 1 个、3,848,817,896 字节（约 3.85 GB / 3.58 GiB）。这是磁盘权重大小，不是推理所需总显存。**DFlash 2 是模型权重的名称，本次 vLLM 的启动方法仍写 `dflash`，不是 `dflash2` 或 `draft_model`。**

以下使用 Linux x86_64、Bash 和 Python 3.12。实测硬件为单张 H100 NVL；需要支持 CUDA 13 的 NVIDIA 驱动，以及目标模型、草稿模型、KV cache 和工作区所需显存。其他 GPU 容量与数值行为需另行验证。

### 2. 准备固定版本

以下命令都在本仓库的 `Deep-Learning/Speculative-Decoding` 目录执行。环境创建仅用于首次安装；已有经过验证的相同版本环境时直接激活，不要重建。下载会占用数十 GB 磁盘空间。

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

模型目录中应包含配置、全部权重分片和目标模型的分词器（tokenizer），不能只下载一个权重分片。上述包版本来自实际安装记录；这里只固定关键包，不保证未来安装时取得的所有间接依赖完全相同。

### 3. 设置三条路线共用的启动参数

在服务端终端执行一次，三种启动方式共用同一个 Bash 数组。目标路径不要包含 `dflash` 字样，避免模型路径识别与实际角色混淆。每次启动的日志保存到 `$HOME/specdec-runs/` 下的独立目录，不覆盖已有结果。

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

关键区别：模型和 KV cache 使用 BF16，但 Mamba SSM cache 固定为 FP32。`max-num-seqs=16` 是服务端调度上限，不是客户端必须发 16 路并发。`generation-config=vllm` 避免模型目录的生成默认值覆盖显式实验设置。

### 4. 选择一种方式启动

**同一 GPU、同一端口只运行其中一条。** 一条路线测完后，在服务端终端按 `Ctrl+C` 停止，并用 `nvidia-smi` 确认该服务已退出，再启动下一条。

基线，不启用推测解码：

```bash
python -I -B -m vllm.entrypoints.openai.api_server "${COMMON[@]}" \
	2>&1 | tee "$RUN_DIR/baseline-server.log"
```

MTP7，使用目标模型自带的 MTP 权重：

```bash
python -I -B -m vllm.entrypoints.openai.api_server "${COMMON[@]}" \
	--speculative-config '{"method":"mtp","num_speculative_tokens":7,"rejection_sample_method":"standard"}' \
	2>&1 | tee "$RUN_DIR/mtp7-server.log"
```

DFlash 2-7，额外加载配套草稿模型权重：

```bash
python -I -B -m vllm.entrypoints.openai.api_server "${COMMON[@]}" \
	--speculative-config "{\"method\":\"dflash\",\"model\":\"$MODEL_ROOT/draft\",\"num_speculative_tokens\":7,\"rejection_sample_method\":\"standard\"}" \
	2>&1 | tee "$RUN_DIR/dflash2_7-server.log"
```

另开同机终端，先检查 `curl --fail http://127.0.0.1:18080/v1/models` 能返回 `Qwen/Qwen3.8-27B`。同时核对启动日志中实际生效的模式、Model Runner V2 和精度；DFlash 应加载 `DFlash2DraftModel`。服务就绪只证明加载完成，还需要下一步真实请求。

### 5. 设置客户端请求与采样

客户端始终调用同一个 `/v1/chat/completions` 和同一个 `model` 名称，**不在客户端切换 MTP/DFlash**。模式由服务端启动参数决定。下面配置的是采样、思考过程、输出上限和请求并发，不包含联网搜索或检索增强生成（RAG）。`top_k=20` 是输出采样范围，不是服务端每轮起草的 7 个 token。

| 客户端设置 | 本次值 |
|---|---|
| 采样 | `temperature=1.0`、`top_p=0.95`、`top_k=20`、`min_p=0.0` |
| 重复惩罚 | `presence_penalty=0.0`、`repetition_penalty=1.0` |
| 思考 | `reasoning_effort="xhigh"`，模板开启并保留思考过程 |
| 输出上限 | `max_completion_tokens=16384`，包含思考过程 |
| 流式统计 | `stream=true`、`include_usage=true`、`return_token_ids=true`、`include_reasoning=true`、`stream_interval=1` |
| 客户端并发 | 正式子集分别为 1、4、8；三次基础随机种子为 20260906、20260907、20260908 |

每题实际随机种子为 `int(SHA256(f"{base_seed}|{task_id}")[:8], 16) % 2147483647`，不是把基础随机种子原样用于每题。[请求样例](experiments/20260906-qwen38/evidence/request-examples.json)保存了当时发送的完整 JSON。下面直接发送其中一份，以保持提示词和参数一致。

在客户端终端进入同一个 `Deep-Learning/Speculative-Decoding` 目录并激活相同 Python 环境，然后执行：

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

`samples[0]` 是代码题，改为 `samples[1]` 可发送数学题。检查完整 SSE 中的生成 `token_ids`、最终 `usage`、`finish_reason` 和 `[DONE]`；`finish_reason=length` 表示触及上限，不能当作正常完成的答案。三条路线应使用相同请求 JSON。此处 curl 的超时与记录方式仅用于单请求复现，不用于计算上文性能表。

### 复现范围

上述命令依据实际安装记录、启动参数及[测量源码](experiments/20260906-qwen38/source/campaign_runner.py)的 `server_command` 整理，将本机路径改为环境变量。**适用范围是三种服务的启动和单个请求的调用，不是完整的性能与质量评测。** 新安装环境仍需验证模型加载与请求结果，不能将已有测试成绩视为新环境的验收结果。

复跑得分表还必须保持同一批 64 题、27 组、固定顺序和并发策略，执行原测量逻辑及 EvalPlus/Math-Verify 评分。`campaign_runner.py` 所需的完整准备步骤、题目输入和调度配置尚未打包为可独立运行的公开入口，因此不能仅凭本页配置直接运行 `--stage all`。现有文件支持启动与调用参考、已保存结果的离线复算，不是完整 27 组实验的独立安装包。官方方法入口：[MTP](https://github.com/vllm-project/vllm/blob/v0.28.0/docs/features/speculative_decoding/mtp.md)、[固定版本推测配置源码](https://github.com/vllm-project/vllm/blob/2cf0a6915ce544dc493a0990f2ea38d81601128a/vllm/config/speculative.py)。

## 测试覆盖与未执行项

原计划包含四个阶段。本文的速度和得分表只使用 S 阶段，兼容性检查和贪心诊断不混入正式子集结果。

| 阶段 | 完成组数 | 实际响应数 | 状态 |
|---|---:|---:|---|
| C：兼容性检查 | 6 | 48 | 已完成 |
| G：贪心诊断 | 36 | 144 | 已完成 |
| S：重复子集 | 27 | 1,728 | 已完成 |
| F：完整题集 | 0 | 0 | 未执行 |

总计完成 **69/81 组、1,920/5,904 份响应**。剩余 12 组、3,984 份响应未执行，既不从计划中删除，也不当作答错。因此，当前结果只覆盖已完成部分，不代表全部计划通过。

F 阶段计划让三条路线在并发 1 和 8 下，分别完成全部 164 道 HumanEval+ 和 500 道 MATH-500，每题一次，随机种子为 20260906。该阶段未执行；已测子集不能写成全量题集成绩。[覆盖记录](experiments/20260906-qwen38/evidence/run.json)保留原计划和未执行项。

### 各阶段测试耗时

| 阶段 | 测量组耗时合计（秒） |
|---|---:|
| 兼容性检查（C） | 928.51 |
| 贪心诊断（G） | 387.09 |
| 重复子集（S） | 27,800.41 |
| 完整题集（F） | 0，未执行 |

这里只累加各测量组从请求派发到响应结束的耗时，不含模型下载、服务启动、预热和评分，显示到小数点后两位；精确值保留在[运行证据](experiments/20260906-qwen38/evidence/run.json)中。测试已完成不表示每份答案都正确。

<a id="previous-experiment-cn"></a>

## 上一轮实验：Qwen3.6-27B 与首代 DFlash（2026-09-05）

上一轮使用 Qwen3.6-27B、首代 DFlash 草稿模型和 vLLM 0.21.0，在同一张 H100 NVL 上完成了全部 164 道 HumanEval+ 和 500 道 MATH-500 的完整答案评测。**DFlash15 单请求更快，主分数与基线相近；但并发 4、8 时，相同 32 道代码题和 32 道数学题的答案质量明显回退。** 根因尚未定位，也未完成修复后复测。

两轮的目标模型、草稿模型、引擎、题目范围和采样设置都不同。本轮新组合没有复现旧组合的严重回退，不能据此认定旧问题已经修好。

### 主评测：完整题集，每题一次

代码需要同时通过官方 EvalPlus 的基础与增强测试，数学由固定版本的官方 Math-Verify 脚本判分。截断回答仍留在分母内。

| 路线 | HumanEval+ | MATH-500 | 代码基础测试 | 数学长度截断 |
|---|---:|---:|---:|---:|
| Baseline | 152/164 (92.68%) | 489/500 (97.80%) | 159/164 | 4 |
| MTP5 | 155/164 (94.51%) | 494/500 (98.80%) | 162/164 | 2 |
| DFlash15 | 153/164 (93.29%) | 490/500 (98.00%) | 160/164 | 3 |

Baseline、MTP5、DFlash15 的代码请求耗时中位数为 4.393、1.175、0.660 秒，数学为 15.666、4.542、2.980 秒；代码输出速率中位数为 53.61、196.01、367.52 tok/s，数学为 54.05、187.60、281.77 tok/s。计时含预填充和同机客户端开销，不含服务启动。先对每一题计算 MTP5 耗时/DFlash15 耗时再取中位数，代码为 1.861 倍、数学为 1.498 倍。5 与 15 个草拟词元不代表相同计算预算，也不是各路线调优后的最佳配置。

![上一轮完整答案请求耗时](images/previous-latency-cn.png)

*作者实测，运行编号 dflash-quality-20260905，每路线代码 164 题、数学 500 题，每题一次。图值来自[逐题复算汇总](experiments/20260905-quality/analysis/summary.json)，由[绘图脚本](tools/make_readme_figures.py)生成。统计所有答案的请求总耗时，不是单独解码算子的时间。*

### 并发质量不能放行

每档使用冻结题目清单的前 32 道代码题和前 32 道数学题，各执行一次。并发数是同机客户端同时在途的请求数，不是每秒到达率。

| 路线 | 并发 | HumanEval+ | 数学子集 | 长度截断（代码/数学） |
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

![上一轮相同题目下的并发正确数](images/previous-concurrency-cn.png)

*作者实测，相同 32+32 题，每档一次。原始响应和官方评分在[结果目录](experiments/20260905-quality/results/)，汇总在[分析结果](experiments/20260905-quality/analysis/summary.json)，图由[绘图脚本](tools/make_readme_figures.py)生成。异常只绑定该轮已测组合，曲线不提供根因证明。*

HumanEval/2 是一个具体例子：三个并发档的规范化请求哈希相同，[并发 1](experiments/20260905-quality/results/dflash15/concurrency-1/repeat-0/HumanEval_2.json) 返回正确函数；[并发 4](experiments/20260905-quality/results/dflash15/concurrency-4/repeat-0/HumanEval_2.json) 返回空定义和 JSON 片段；[并发 8](experiments/20260905-quality/results/dflash15/concurrency-8/repeat-0/HumanEval_2.json) 出现无关函数名和重复文本，耗尽 4,096 个词元后截断。这套 DFlash15 配置不能凭单请求结果直接承载并发流量；现有证据也不能把原因归结为某个 vLLM 组件、浮点误差、DFlash 理论、H100 或云平台。

三条主路线各 1,012 份响应（主评测 664、同种子重复 48、流式 48、并发 192、随机采样 48、合成检索 12），加上 DFlash5 的 64 份同窗口结果，合计 **3,100 份响应、25 个路线/场景组合**。DFlash5 代码和数学均为 32/32，其并发未测试。

### 上一轮的固定方法

| 项目 | 记录值 |
|---|---|
| GPU | 一张 NVIDIA H100 NVL，95,830 MiB；驱动 610.57.04 |
| 目标模型 | `Qwen/Qwen3.6-27B` @ `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`，BF16 |
| 草稿模型 | `z-lab/Qwen3.6-27B-DFlash` @ `0919688658996800f86b895034249700e9481106` |
| 生成环境 | vLLM 0.21.0，PyTorch 2.11.0，transformers 4.57.6 |
| 评分器 | EvalPlus @ `26d6d00bb1fd0fa37f39c99d5290da67891d1c5e`；Math-Verify @ `ba3d3aaff23b3f4cac7a14672b4f6e293d97c98b` |
| 数据集 | HumanEval+ v0.1.10；MATH-500 @ `6e4ed1a2a79af7d8630a6b768ec859cb5af4d3be` |
| 主评测采样 | temperature 0，top_p 1，top_k -1，seed 20260905；`enable_thinking=false` |
| 服务参数 | max_model_len 40960，max_num_seqs 16，max_num_batched_tokens 8192，显存比例 0.9，关闭 prefix caching |
| 输出预算 | 代码 4096，数学 8192 |

模型、配置和分词器的文件哈希及包版本在 [inputs.json](experiments/20260905-quality/metadata/inputs.json)；[公开协议](experiments/20260905-quality/src/experiment.json)仅移除了私有资源管理对象，[投影说明](experiments/20260905-quality/metadata/protocol-public-projection.json)记录变更前后哈希。代码评分在无网络、非特权 Docker 容器内执行。

<details>
<summary>在新目录重跑上一轮生成（需要 H100 NVL 与 Docker）</summary>

需要 Linux、Python 3.12、兼容的 H100 NVL 环境及容纳两个权重快照和依赖的磁盘空间。评分容器按 UID/GID 1000 执行，宿主需要能用 `sudo -n` 调用 Docker。从 `experiments/20260905-quality` 目录开始，新建运行目录，不覆盖提供的证据。

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

生成 CLI 只停止自己的模型服务，不会释放宿主机。复跑时应对照[评分依赖版本](experiments/20260905-quality/metadata/evaluator-requirements-frozen.txt)和[原镜像 ID](experiments/20260905-quality/metadata/evaluator-image-id.txt)；即使评分源码 commit 固定，Docker 基础标签和系统包仍可能变化。vLLM 0.21.0 接受 `standard`、不接受 `strict`；目标路径若含 `dflash` 可能触发方法推断误判。

</details>

<a id="research-history-cn"></a>

## 早期研究资产（2026 年上半年）

以下内容早于两轮正式评测，使用不同的模型、引擎版本和方法，只作为脚本、配置与数据的来源说明，不作为当前参数建议或质量保证。

| 阶段 | 做了什么 | 记录的结果 |
|---|---|---|
| 官方 EAGLE3 模型验证 | 用官方 Llama-3.1-8B EAGLE3 草稿头部署 vLLM，20 次运行、每次 512 token | 平均 441.7 tok/s，基线 165.7 tok/s，约 2.67 倍 |
| 自训练 EAGLE3 草稿头 | 用 SpecForge 在单张 H100 上训练约 45 分钟 | 代码生成 1.30 倍；技术问答与数学约 1.00 倍；创意写作 0.84 倍 |
| H100 三路线速度样例（2026-06-28） | Qwen3.6-27B：vLLM 原生 MTP（5 候选）、vLLM DFlash（15 候选）、llama.cpp MTP Q4_K_XL；每类任务 3 次取中位数 | Coding 中位 TPS 分别为 146.7、191.7、107.3 |

2026-06-28 的速度样例是**限长输出**，两条 vLLM 路线的 18 条正式记录全部以 `finish_reason="length"` 结束，没有答案评分，也没有测 TTFT；候选数不同，不能据此给算法排名。完整答案质量评测从上一轮实验开始才独立进行。

| 资产 | 内容 |
|---|---|
| [`config/`](config/) | EAGLE3 训练/部署配置 `eagle3_llama31_8b.yaml`，以及 Llama-3.1-8B EAGLE3 草稿头结构配置 `llama3-8B-eagle3.json` |
| [`scripts/`](scripts/) | EAGLE3 服务启动与训练脚本、训练数据准备脚本；Qwen3.6 的 vLLM MTP/DFlash 与 llama.cpp MTP 启动脚本；三路线 benchmark 客户端与编排脚本 |
| [`data/`](data/) | 2026-06-28 三路线的原始 benchmark 结果 `h100_vllm_native_mtp.json`、`h100_vllm_dflash.json`、`h100_llamacpp_mtp_q4kxl.json` |
| [`logs/`](logs/) | EAGLE3 服务启动与训练样例日志、三路线服务启动日志 |
| [`images/`](images/) | EAGLE3 架构图、训练对比图和 EAGLE/MTP 参数示意图，以及本文使用的中文结果图 |
| [`tools/make_readme_figures.py`](tools/make_readme_figures.py) | 从两轮实验的已发布汇总数据重新生成本文的中文结果图，需要 Matplotlib 和中文字体 |
| [`test_performance.py`](test_performance.py)、[`requirements.txt`](requirements.txt) | 早期性能测试脚本及其依赖 |

## 证据与代码

| 入口 | 可核对的内容 |
|---|---|
| [执行程序](experiments/20260906-qwen38/source/campaign_runner.py) | 当时使用的组派发、计时和实验控制代码 |
| [评分接入](experiments/20260906-qwen38/source/scoring.py)、[流式计时](experiments/20260906-qwen38/source/stream_metrics.py) | 官方评分与回答如何绑定，token 如何核对，延迟如何计算 |
| [配置](experiments/20260906-qwen38/evidence/configuration.json)、[请求样例](experiments/20260906-qwen38/evidence/request-examples.json) | 固定参数及两份带哈希的实际请求 |
| [实验记录](experiments/20260906-qwen38/evidence/run.json) | 测试覆盖、加载检查、测量耗时及来源成员哈希 |
| [逐组记录](experiments/20260906-qwen38/data/groups.json)、[数值汇总](experiments/20260906-qwen38/data/summary.json) | 题目 ID、已存评分、计时、计数和配对结果 |
| [分析程序](experiments/20260906-qwen38/analyze_results.py)、[验收程序](experiments/20260906-qwen38/validate_report.py)、[测试](experiments/20260906-qwen38/test_report.py) | 重新汇总数字，检查本文表格、链接、徽章和证据是否一致 |
| [上一轮分析](experiments/20260905-quality/analysis/)、[上一轮结果](experiments/20260905-quality/results/)、[上一轮源码](experiments/20260905-quality/src/) | 2026-09-05 的逐题对照、原始响应、官方评分和分析程序 |

这些源码是实际执行版本的归档，不是从零部署 GPU 的完整安装包。**完整原始回答和 SSE 流仍在作者的私有归档中，没有在此重新分发。** 公开文件不含基础设施定位信息或凭据；归档及成员哈希说明来源，但不能独立证明运行行为。

## 离线复算

在 `Deep-Learning/Speculative-Decoding` 目录执行，使用 Python 3.10+ 标准库，无需额外依赖、GPU、网络或凭据：

```bash
python experiments/20260906-qwen38/validate_report.py
python -m unittest discover -s experiments/20260906-qwen38 -p "test_*.py"
```

验收应输出 `REPORT_GATE=PASS`，测试全部通过，两条命令的退出码都为 0。它们检查本文表格、已保存的评分和文件哈希是否一致，不发起新推理，也不重新评分。专用 CI 在 Windows、Linux 的 Python 3.10 和 3.12 上执行这些检查。

要从逐组数据独立核对汇总数字，可执行：

```bash
python experiments/20260906-qwen38/analyze_results.py --groups experiments/20260906-qwen38/data/groups.json --output experiments/20260906-qwen38/regenerated
```

输出目录中的 `summary.json` 可与[已发布汇总](experiments/20260906-qwen38/data/summary.json)对照。程序只读取已保存的评分、计数和计时，不执行生成的答案。

上一轮实验的复算需要 Python 3.12，检查全部 3,100 个请求、固定题集、题目/重复次数和评分绑定；缺题或错配会失败，不会缩小分母后报分：

```bash
python experiments/20260905-quality/src/analyze_results.py --root experiments/20260905-quality --output out/20260905-replayed.json --matrix
```

## 结论适用到哪里

- 可以说明本次固定配置、固定子集中的性能和得分，不能证明统计显著性、分布等价或正式非劣效。
- 吞吐、客户端延迟、正确答案交付速度是不同指标，不能互相替代，也不能据此推断 GPU kernel 的独立性能。
- 本轮换了模型、权重版本和引擎，不能据此认定上一轮 DFlash 的并发故障已修复。两轮结果独立保留。

## 官方资料

- [经典推测解码方法](https://proceedings.mlr.press/v202/leviathan23a.html)
- [DFlash 论文](https://arxiv.org/abs/2602.06036)与[项目代码](https://github.com/z-lab/dflash)
- [vLLM 0.28.0](https://github.com/vllm-project/vllm/releases/tag/v0.28.0)
- [EvalPlus](https://github.com/evalplus/evalplus)与 [MATH-500 来源](https://github.com/openai/prm800k#math-splits)
- [EAGLE](https://github.com/SafeAILab/EAGLE)与 [SpecForge](https://github.com/SafeAILab/SpecForge)
