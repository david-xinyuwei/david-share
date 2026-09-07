# Qwen3.6-27B: Complete-Answer DFlash / MTP Regression

[中文](README-CN.md) | English

**The experiment completed; the DFlash15 concurrent deployment did not pass the observed quality check.** On this single H100 NVL configuration, DFlash15 reduced serial request latency, with primary scores close to the baseline. At concurrency 4 and 8 it produced materially worse answers on the same 32 code and 32 math tasks. The cause is unresolved and no fix has been validated.

This is an author-run deployment regression dated 2026-09-05 UTC, not a complete reproduction of the DFlash paper, a statistical noninferiority study, or Microsoft product certification. The June three-prompt speed samples in the parent directory remain a separate experiment.

## Results

Each primary route generated one answer for every HumanEval+ task and every MATH-500 task. Code passes require both the official EvalPlus base and extra tests. Math uses the pinned official Math-Verify evaluator. Truncated outputs remain in the denominator.

| Route | HumanEval+ | MATH-500 | Code base tests | Math length stops |
|---|---:|---:|---:|---:|
| Baseline | 152/164 (92.68%) | 489/500 (97.80%) | 159/164 | 4 |
| MTP5 | 155/164 (94.51%) | 494/500 (98.80%) | 162/164 | 2 |
| DFlash15 | 153/164 (93.29%) | 490/500 (98.00%) | 160/164 | 3 |

All primary code responses stopped normally. No primary response had empty content. These are public datasets; training exposure is unverified, so the scores are not a guarantee on private business workloads.

![Complete-answer latency](analysis/figures/primary-latency.png)

*Author-run measurement, run `dflash-quality-20260905`, one response per task, 164 code and 500 math tasks per route. Figure values come from [the reconciled summary](analysis/summary.json). Inspect complete-request latency, not an isolated decode-kernel time. All answers are included, not only correct ones; output lengths may differ.*

Median request times for Baseline/MTP5/DFlash15 were 4.393/1.175/0.660 seconds on code and 15.666/4.542/2.980 seconds on math. They include prefill and same-host client overhead, but exclude server startup. The corresponding median output rates were 53.61/196.01/367.52 and 54.05/187.60/281.77 tokens/s. Rates use server-reported completion tokens divided by request time.

The median of **per-task** MTP5/DFlash15 latency ratios was 1.861 on code and 1.498 on math. This is not the ratio of column medians. Routes ran sequentially, the complete primary dataset was not repeated, and the 5-versus-15 draft windows do not establish equal compute budgets or tuned optima.

## Equal Scores Are Not Equal Answers

- Relative to Baseline, DFlash15 changed one passing code answer to failing and two failing answers to passing. For math, the counts were two regressions and three improvements.
- Exact response text matched in 135/164 code tasks and 178/500 math tasks. Text equality and correctness are separate measurements; token-ID equality was not captured.
- Relative to MTP5, DFlash15 passed two fewer code tasks. Five math answers changed from pass to fail and one from fail to pass, a net decrease of four.
- Small score differences do not demonstrate changed model capability or prove noninferiority. A conditional sampling theorem does not validate every serving implementation.

Inspect [Baseline versus DFlash15](analysis/baseline-vs-dflash15.csv) and [MTP5 versus DFlash15](analysis/mtp5-vs-dflash15.csv) for both directions of every task-level difference.

## Concurrent Quality Failure

Each setting used the first 32 code and 32 math tasks in the frozen manifest, once each. Concurrency means simultaneous client requests to the same local server, not arrival rate or production traffic.

| Route | Concurrency | HumanEval+ | Math subset | Length stops, code / math |
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

![Correctness under concurrency](analysis/figures/concurrency-quality.png)

*Author-run measurement, the same 32+32 task subset and one run per setting. See [raw response and scorer directories](results/) and [the summary](analysis/summary.json). The observed regression is specific to this tested stack; its cause is not established.*

For HumanEval/2, the canonicalized request hash was identical across concurrency 1/4/8: `a2d36850694048f29a3449df499ddf831d55fd6219b7ddad9bba21a7635701ab`. At [concurrency 1](results/dflash15/concurrency-1/repeat-0/HumanEval_2.json), the response implemented `truncate_number` in 97 tokens. At [concurrency 4](results/dflash15/concurrency-4/repeat-0/HumanEval_2.json), it returned an empty `solution` definition and a JSON fragment. At [concurrency 8](results/dflash15/concurrency-8/repeat-0/HumanEval_2.json), it introduced an unrelated function name, repeated text and reached the 4,096-token budget.

The analyzer verifies requests against the frozen tasks and links each saved answer to official scoring input and output. `samples.jsonl` contains generated answers for the grader; it is not the prompt dataset. Its changed hash is not evidence that the prompts changed.

Do not deploy this exact DFlash15 configuration for concurrent traffic based only on its serial results. The evidence does not identify a particular vLLM component, floating-point effect, DFlash theory, GPU, or cloud platform as the cause. No corrected configuration was retested.

## Supplementary Coverage

| Group | Responses per primary route | Observed scope |
|---|---:|---|
| Primary | 664 | 164 code + 500 math, one answer each |
| Same-seed repeats | 48 | 16 tasks x 3; no text or correctness changes observed |
| Streaming | 48 | Same 16 tasks x 3; first nonempty output and final usage recorded |
| Concurrency 1 / 4 / 8 | 192 | 64 tasks at each level, one run |
| Sampling | 48 | 16 tasks x 3 seeds, temperature 0.7, top_p 0.9; all scored correctly |
| Synthetic retrieval | 12 | 4,123 / 16,416 / 32,796 actual input tokens, four positions each; all correct |

The three primary routes each have 1,012 responses. DFlash5 adds 64 matched-window responses, giving **3,100 responses across 25 route/group combinations**. Canary attempts are excluded.

DFlash5 passed 32/32 code and 32/32 math tasks. Median per-task MTP5/DFlash5 latency ratios on those matching primary tasks were 1.087 and 1.046. Five candidate tokens are not equal compute cost. DFlash5 concurrency was not tested.

Streaming median first-nonempty-output latency, code/math: Baseline 54.1/51.4 ms; MTP5 63.5/56.9 ms; DFlash15 60.0/54.7 ms. This subset did not show TTFT acceleration and does not represent Internet latency. Repetition and sampling subsets are small and easy; they do not prove full-dataset stability or distribution equality. Synthetic retrieval is not long-document reasoning.

Acceptance metrics use genuine Prometheus counter differences over each route's **entire process**, including supplemental groups. They are not primary-only acceptance rates, and the windows and workload mixes differ. Full raw counter snapshots are retained.

## Frozen Method

| Item | Recorded value |
|---|---|
| GPU | One NVIDIA H100 NVL, 95,830 MiB; driver 610.57.04 |
| Target | `Qwen/Qwen3.6-27B` @ `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`, BF16 |
| Drafter | `z-lab/Qwen3.6-27B-DFlash` @ `0919688658996800f86b895034249700e9481106` |
| Generation runtime | vLLM 0.21.0, PyTorch 2.11.0, transformers 4.57.6 |
| Graders | EvalPlus @ `26d6d00bb1fd0fa37f39c99d5290da67891d1c5e`; Math-Verify @ `ba3d3aaff23b3f4cac7a14672b4f6e293d97c98b` |
| Datasets | HumanEval+ v0.1.10; MATH-500 @ `6e4ed1a2a79af7d8630a6b768ec859cb5af4d3be` |
| Primary sampling | temperature 0, top_p 1, top_k -1, seed 20260905 |
| Thinking | `chat_template_kwargs={"enable_thinking": false}` |
| Serving | max_model_len 40960, max_num_seqs 16, max_num_batched_tokens 8192, GPU memory utilization 0.9, prefix caching off |
| Rejection method | vLLM `standard`, not `synthetic`; primary generation uses its greedy branch |
| Output budgets | Code 4096, math 8192 |

Model/config/tokenizer file hashes and package versions are in [inputs.json](metadata/inputs.json). The scorer is an unprivileged, network-disabled Docker container; generated code did not run directly on the VM host. Official sanitizer extraction is preserved along with both raw and extracted samples. The scorer's dependency versions are recorded separately from the generation environment.

The original protocol hash is `a379ab0f25d801e5a8e38419331586962b3299192aa8c648ce450e6b8ef82c47`; task-manifest hash is `6e9ed5aeae30acf98257714dc915ad3c28c41b14c12dd125021424cd185b8dae`. The [public protocol](src/experiment.json) removes only the private resource-management object; [projection provenance](metadata/protocol-public-projection.json) records both hashes. Raw response hashes and scientific fields are unchanged. This projection is not a claim that readers can reconstruct the private original.

## Recompute Without A GPU

From this experiment directory, Python 3.12 and the standard library are sufficient:

```bash
python src/analyze_results.py --root . --output analysis/summary.json --matrix
```

The analyzer checks all 3,100 requests, the fixed task manifest, task/repetition sets and grader bindings. It rejects a missing sample or mismatched answer instead of reporting a smaller denominator. This command was run successfully against both the local original and this public projection.

To render the measured figures with the recorded Matplotlib dependency:

```bash
python src/make_quality_figures.py --summary analysis/summary.json --output analysis/figures
```

## Generate A Fresh Run

Use Linux, Python 3.12, a compatible H100 NVL setup and sufficient disk space for both model snapshots and the runtime. The recorded scoring container uses UID/GID 1000 and requires noninteractive Docker access via `sudo -n`. This is paid GPU work; an offline recomputation above does not require it. Start in this experiment directory and use a new run directory, never the supplied evidence directory.

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

The private cloud start/stop controller is intentionally not included. The generation CLI stops its own model servers, not the host VM. A fresh reconstruction on a second machine was not executed for this delivery; compare its dependency versions and image ID with [the captured scorer dependencies](metadata/evaluator-requirements-frozen.txt) and [image ID](metadata/evaluator-image-id.txt). The Docker base tag and system packages may move even when the evaluator commits are fixed.

Two observed setup traps are captured in the runnable code: vLLM 0.21.0 requires `standard`, not `strict`, and a target path containing `dflash` can trigger its method-detection heuristic for MTP. Use a neutral target path. EvalPlus sanitize has no `--dataset` argument and reads both HumanEval+ and MBPP+; its fixed auxiliary MBPP+ input is provided offline without enabling network access for generated code.

## Evidence Boundaries

- [Export manifest](metadata/public-export.json): file sizes, original-copy hashes and the explicitly identified protocol projection.
- [Summary](analysis/summary.json), [per-task comparisons](analysis/) and [raw responses / official scores](results/) are preserved, including negative results.
- The original evidence bundle was collected and hash-verified before the GPU VM was deallocated. Administrative logs, cloud identifiers and credentials are intentionally not public; full private evidence remains with the author.
- No universal accuracy, distribution-equivalence, production-readiness or cross-version claim follows from this run. The DFlash15 concurrency failure remains unresolved.