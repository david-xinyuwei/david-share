# Validation: Component Precision and Resource Accounting

[中文](VALIDATION_CN.md) · [Main guide](README.md) · [Data](data/model-evidence.json)

## Scope

The executable tool reads public metadata or replays a saved snapshot and calculates tensor payload bytes. It does not run models, provision GPUs, determine production GPU counts, or generate throughput/quality scores.

Capture times are `2026-11-01T12:49:24.528Z` for model metadata and `2026-11-01T12:51:18.489Z` for original NVFP4 configuration summaries, both UTC. The data retains model IDs, pinned revisions, observed read status and scope. A checkpoint publisher and an original model developer are different identities.

## Replay and tests

Requires Node.js 20+ with no npm dependencies. Use PowerShell or Bash from this directory. Absolute script paths also work from another working directory because data is resolved relative to the module, not the current directory.

```bash
node tools/inspect.mjs
node --test tests/inspect.test.mjs tests/census.test.mjs tests/mi300x.test.mjs
```

Successful replay emits JSON with `result_type=CALCULATED_FROM_PUBLIC_METADATA` and inference status `NOT_RUN`. `tensor_payload_bytes` sums per-dtype element counts times storage bytes. GB is decimal and GiB binary. Headers, non-tensor files, KV/state caches, runtime workspaces and communication buffers are excluded.

The sixteen tests: `inspect.test.mjs` (eight) covers three complete component tables with bilingual references/local links, independent repository prose, packed U8 accounting, the six observed payloads, retained Muse HTTP 401, Nemotron router exclusions, unknown dtypes, fresh revisions invalidating old configuration evidence, and HTTP failure without silently replaying old data. `census.test.mjs` (four) checks census-to-API byte parity, key component dtypes and tensor counts for both models, and rejection of unclassified components or a tampered total. `mi300x.test.mjs` (four) checks that every number in `data/mi300x-run/summary.json` traces back to its raw request/response/log file, that the public projection contains no private identifiers, that the Nemotron and Inkling numbers quoted in all four documents equal the summary, and that the documents claim no throughput/quality acceptance or Muse run. HTTP objects in tests are unit-test stubs, not live model evidence.

## Fresh metadata

```bash
node tools/inspect.mjs --live
```

This rereads the public API for the six model IDs. Check the returned capture time and revisions before comparing payloads. The refresh clears old configuration summaries because it does not re-inspect the large quantization files. HTTP errors, unknown dtypes or identity changes fail rather than masquerading as current data.

No model-download credentials are needed or expected. Muse's gated raw quantization configuration is a separate disclosed gap; do not bypass it through another account or mirror.

## Preserve source anomalies

Nemotron BF16's reported `safetensors.total` differs from the sum of its per-dtype counts. The tool reports both values and `metadata_total_matches=false`, calculates bytes from per-dtype counts and does not modify the source record. Packed `U8` elements and scale tensors in a quantized export are not the original logical parameter count.

## Model acceptance

Follow the model's own official recipe linked from the [main guide](README.md#select-a-verifiable-path-before-starting-a-service). Record weight SHA, engine commit/image digest, GPUs, parallel topology, selected kernels, cache/state dtypes, exact business requests and results. Use the same real tasks across BF16, FP8 and NVFP4; unexecuted combinations remain `NOT_RUN` rather than borrowing another model's results.

Cover required modalities, structured output, tool calls, quality, long context, target concurrency, peak VRAM and sustained operation. Loading is not business success, and low-bit storage is not native low-bit computation.

## Current status

| Check | Status and scope |
|---|---|
| Public identities and six pinned revisions | Read from the API; the two BF16 releases were downloaded in full on 2026-11-02 (Nemotron 3 Ultra 1,121,078,235,607 bytes, Inkling 1,904,787,107,666 bytes); the other seven were not downloaded |
| Original NVFP4 configuration | Nemotron and Inkling parsed; Muse returned 401 and was not parsed |
| Per-tensor dtype census | PASS for the two BF16 releases: 51,023 + 1,552 tensors read from safetensors headers; header byte totals equal the API metadata; no unclassified name pattern (see "Per-tensor dtype census") |
| File diagnostics | Editor checks executed; not evidence that Node tests passed |
| Node tests and CLI | PASS: sixteen tests, zero failures (`node --test tests/inspect.test.mjs tests/census.test.mjs tests/mi300x.test.mjs`); three four-column tables with 25 items each, all nine releases, bilingual references/local links, six payload calculations, census-to-API byte parity, key component dtypes, and every MI300X number quoted in the documents equal to `data/mi300x-run/summary.json` |
| Table layout | PASS: all tables on four pages checked at 1280 and 390 px; table and container widths were inspected separately, with no horizontal table overflow |
| Full local preview | The script-completion wait timed out in this revision; this is not a successful full-render check. Figure bytes and diagram source remain unchanged; GitHub rendering is checked separately |
| MI300X BF16 load and smoke, Nemotron 3 Ultra | PASS on 8 × MI300X (attempt 3): engine ready, two requests answered correctly; kernels, cache precision and memory recorded in "MI300X run" |
| MI300X BF16 load and smoke, Inkling | PASS on 2 × 8 MI300X (attempt 6, TP8 × PP2): engine ready, three requests answered, the `max_tokens=1024` request gave a correct final answer; the TP8 × DP2 + EP16 layout (attempt 5) became ready and then hung on its second request, recorded as not passing in this image |
| MI300X BF16 load and smoke, Muse Spark Open | BLOCKED: both Meta repositories are manually approved gated repositories; a `config.json` read on 2026-11-02 returned 403 `GatedRepo`; the access request is submitted and the weights cannot be downloaded before approval |
| Throughput, latency, business-task quality, long context, production stability | NOT_RUN for all three models |
| NVFP4 releases: load path on MI300X | NOT_RUN; publisher statements cover Blackwell/Hopper only, and whether vLLM ROCm rejects or dequantizes a ModelOpt NVFP4 checkpoint is unverified |
| FP8 releases on any GPU | NOT_RUN; outside this round's measurement scope |
| Independent Chinese and bilingual semantic review | PASS for this revision: five wording, condition and source-link findings were repaired and independently rechecked; not a visual or inference test |
| GitHub publication and live pages | Refer to this project's public commit and check results; local preview does not establish live-page acceptance |

An unexecuted check cannot be labeled PASS. Public-source analysis, mechanism explanation and executable tools have separate acceptance boundaries.

Independent text review covers the four bilingual documents and component tables; a focused second pass rechecked all five findings against the repaired text. `AI_NATIVE_CHINESE_AUDIT=PASS` and `AI_BILINGUAL_SEMANTIC_AUDIT=PASS`. It does not execute models, rerun performance tests or replace component-level runtime verification. Deterministic source-cell parity and local-link checks passed separately.

## Rebuild the document preview

Use PowerShell 7's built-in `ConvertFrom-Markdown`; no npm packages are installed. Browser-side Mermaid and KaTeX rendering requires the pinned public CDN assets in the script. From this project directory:

```powershell
./tools/preview.ps1 -OutputDirectory "$env:TEMP/large-moe-guide-preview"
```

One entry generates all four pages and records source/HTML SHA-256 values. Each model uses a four-column table retaining every component and release, with no horizontal table scrolling required. Compare each table's `scrollWidth` and `clientWidth` and inspect actual screenshots. Official figure provenance, dimensions and SHA-256 are in [visual-evidence.json](data/visual-evidence.json). Local preview is not GitHub publication acceptance or independent bilingual semantic review.

## Per-tensor dtype census

```bash
python3 tools/tensor_census.py <snapshot_dir> <out.json>   # on the host that holds the downloaded checkpoint; header-only read
node tools/census.mjs --table                               # summarize data/tensor-census/*.json locally and cross-check against API metadata
```

`tensor_census.py` reads each `.safetensors` file's 8-byte header length and JSON header, yielding every tensor's name, dtype, shape and byte range without reading weight data or touching a GPU. Tensor names are classified into components by regular expression (embedding, attention, router, routed experts, shared experts, latent projection, Mamba projection, Mamba state parameters, short convolution, norm/bias, encoders, dense MLP, MTP, output head); unmatched name patterns are reported under `unmatched_patterns_top`, which the tests require to be empty.

| Model and revision | Files | Tensors | Header bytes total | Versus API-metadata bytes |
|---|---:|---:|---:|---|
| Nemotron 3 Ultra BF16 `77df655d` | 225 | 51,023 | 1,121,049,257,984 | equal |
| Inkling BF16 `828496ee` | 109 | 1,552 | 1,904,755,280,148 | equal |

The census ran on 2026-11-02 on Azure `Standard_ND96isr_MI300X_v5` against fully downloaded snapshots; results are in [data/tensor-census/](data/tensor-census/). `node --test tests/census.test.mjs` checks byte agreement with `model-evidence.json`, decisive component dtypes and counts (such as Nemotron's 48 F32 `e_score_correction_bias` router tensors, Inkling's 128 fused expert tensors and 128 F32 scalars), and rejection of unclassified components.

## MI300X run

<a id="mi300x-run"></a>

**Question.** None of the three publishers documents a BF16 deployment on MI300X. On 2026-11-02 this project loaded the models on two Azure `Standard_ND96isr_MI300X_v5` Spot VMs (8 × MI300X 192 GB each) to answer: do the original BF16 weights load under vLLM ROCm, which kernels are actually selected, what precision do the caches use, and how much memory is consumed.

**Environment.** Host Ubuntu 24.04.5, kernel `6.8.0-1067-azure`, ROCm 6.4.4 (amdgpu 6.12.12); container `rocm/vllm:rocm10.1.0_ubuntu24.04_py3.14-pytorch_2.13.0_vllm-0.29.0` (image ID `e0ea9a10…`, vLLM `0.29.1.dev0+g98dff2a81`, torch `2.13.0+rocm10.1.0`, Triton 3.8.0, aiter installed). Weights on a RAID0 of 8 × 3.5 TB local NVMe. Container flags `--network host --ipc host --device /dev/kfd --device /dev/dri --ulimit memlock=-1:-1 --shm-size 64g`.

### Nemotron 3 Ultra BF16, one node, 8 GPUs

Launch (aligned with the model card's vLLM example minus CUDA-only options):

```bash
vllm serve nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16 --revision 77df655d5e9f8362164ed14dd8b48f8bce657498 \
  --trust-remote-code --dtype bfloat16 --tensor-parallel-size 8 --enable-expert-parallel \
  --max-model-len 65536 --gpu-memory-utilization 0.90 --max-num-seqs 16 --max-num-batched-tokens 16384 \
  --enable-chunked-prefill --enable-prefix-caching --mamba-ssm-cache-dtype float16 --reasoning-parser nemotron_v3
# env: VLLM_ROCM_USE_AITER=1 VLLM_ROCM_USE_AITER_MOE=0
```

Three attempts, one variable changed each time:

| Attempt | Change | Outcome | Root cause in the log |
|---|---|---|---|
| 1 | Defaults (AITER MoE on) | Failed while building the model | `ValueError: Unquantized MoE backend ROCm AITER does not support the deployment configuration since kernel does not support no act_and_mul MLP layer` — LatentMoE experts are non-gated `relu2` MLPs; the AITER fused-MoE kernel requires the act_and_mul structure |
| 2 | `VLLM_ROCM_USE_AITER_MOE=0` | Weights loaded (136.51 GiB/GPU, 443 s), failed during Mamba2 kernel warm-up | `mamba_ssm.py selective_state_update … PHILOX_ROUNDS` → `LLD failed to link hsaco … ld.lld: error: target emulation unknown`; a minimal Triton kernel compiles and runs in the same image, so the failure is specific to the stochastic-rounding SSU kernel |
| 3 | Also drop `--enable-mamba-cache-stochastic-rounding` | **Ready and generating** | — |

Decisive log lines from attempt 3 (rank 0):

```text
Using TRITON Unquantized MoE backend out of potential backends: ['TRITON', 'BATCHED_TRITON']
Using TritonExperts MoE backend
Found incompatible backend(s) [TURBOQUANT] with AttentionType.DECODER. Overriding with ROCM_ATTN out of potential backends: ['ROCM_ATTN', 'ROCM_AITER_FA', 'ROCM_AITER_UNIFIED_ATTN', 'TRITON_ATTN']
Using ['AITER_CUSTOM', 'PYNCCL'] all-reduce backends … for group 'tp:0'   /   Using ['PYNCCL'] … for group 'ep:0'
Using triton Mamba SSU backend
Using SSM config from …/selective_state_update/headdim=64,dstate=128,device_name=AMD_Instinct_MI300X,cache_dtype=float16.json
Setting attention block size to 1056 tokens to ensure that attention page size is >= mamba page size
Model loading took 136.51 GiB memory and 111.97 seconds          # warm second load; cold first load 443 s
Available KV cache memory: 23.07 GiB
GPU KV cache size: 3,490,022 tokens, Maximum concurrency for 65,536 tokens per request: 53.25x
Free memory on device (186.12/191.45 GiB) … Actual usage is 146.67 GiB for consumed memory (weights + non-torch), 2.57 GiB for peak activation
init engine (profile, create kv cache, warmup model) took 119.58 s (compilation: 22.31 s)
```

Two smoke requests (`temperature=0`; verbatim inputs in `evidence/nemotron_bf16_8xMI300X/02_smoke_request.json`, `03_smoke2_request.json`):

| Request | Input | Output tokens (reasoning) | Wall time | Content check |
|---|---|---:|---:|---|
| Chinese, "one sentence on BF16 vs FP16", `max_tokens=200` | 31 tokens | 94 (21) | 1.61 s | Correct: BF16 7-bit mantissa + 8-bit exponent, FP16 5-bit exponent + 10-bit mantissa |
| English, three differences Mamba-2 vs softmax attention, `max_tokens=256` | 42 tokens | 209 (29) | 5.42 s | Coherent: linear vs quadratic complexity, fixed state vs full KV, parallelism |

This establishes only that the model loads, generates, and uses the kernels and cache precisions above; it is not throughput, quality or long-context acceptance. Evidence: [data/mi300x-run/nemotron_bf16_8xMI300X/](data/mi300x-run/nemotron_bf16_8xMI300X/) (requests, responses, `rocm-smi` JSON, server-log key lines, `00_meta.txt`); the full container log and the three attempt logs stay in the author's private evidence directory because of size, with their SHA-256 values listed in `SHA256SUMS.private.txt` in the same directory. Every number quoted in this section is recomputed from those raw files by `tools/mi300x_evidence.py summarize` and checked by `tests/mi300x.test.mjs`.

### Inkling BF16, two nodes, 16 GPUs

Each node holds a full snapshot (1,904,787,107,666 bytes); the container adds `--device /dev/infiniband`, and Ray spans the two nodes. RCCL environment: `NCCL_IB_HCA=^mlx5_8:1,mlx5_an0:1 NCCL_NET_GDR_LEVEL=0 NCCL_IB_PCI_RELAXED_ORDERING=1 GLOO_SOCKET_IFNAME=eth0`. Launch command (attempt 5 layout):

```bash
vllm serve thinkingmachines/Inkling --revision 828496eeae4c243ff1a22f7f28ff83694f2f7bc9 \
  --trust-remote-code --dtype bfloat16 --tokenizer-mode inkling --reasoning-parser inkling \
  --tensor-parallel-size 8 --data-parallel-size 2 --data-parallel-size-local 1 --data-parallel-backend ray --enable-expert-parallel \
  --max-model-len 65536 --gpu-memory-utilization 0.90 --max-num-seqs 16 --max-num-batched-tokens 16384 \
  --enable-chunked-prefill --distributed-timeout-seconds 3600 --kernel-config '{"enable_jit_warmup": false}'
# environment: VLLM_ROCM_USE_AITER=1 (the AITER fused MoE kernel accepts Inkling's gated SwiGLU experts)
```

Six attempts, one variable changed each time:

| Attempt | Layout and change | Result | Root cause in the log |
|---|---|---|---|
| 1 | TP16, `NCCL_IB_HCA` allow-list, default GPU Direct RDMA | RCCL initialisation hung for more than 8 minutes | `Peermem not available, falling back to GPU Direct RDMA (DMAbuf)` and then no `Init COMPLETE`. A `torchrun` 16-rank all_reduce probe in the same image: same environment times out; with `NCCL_NET_GDR_LEVEL=0` it passes (64 MiB all_reduce 2.4 ms, busbw 52.4 GB/s) |
| 2 | TP16, `NCCL_NET_GDR_LEVEL=0` | All 16 ranks reached model construction and were rejected by the model itself | `Error: sconv SWA cache supports tp_size <= num_kv_heads (8), got 16` — the sliding-window short-convolution cache shards at most 8 ways, matching the model card's multi-node recipe "TP within a node, DP across nodes, EP over all ranks" |
| 3 | TP8 × DP2 + EP16 (Ray) | Failed at start | `Not enough resources to allocate 2 DP ranks on DP master node <node0-private-ip>, possible to fit 1 DP ranks` — Ray DP places every DP rank on the master unless told otherwise |
| 4 | Add `--data-parallel-size-local 1` | Weights loaded on all 16 ranks, AITER MoE selected, HIP graphs captured, then warm-up failed | `kernel_warmup → fa4_cutedsl_warmup → _warm_inkling_fa4_rel_attention` imports the CUDA-only `vllm.vllm_flash_attn` → `ImportError: … requires the CUDA flash attention extensions (_vllm_fa2_C or _vllm_fa3_C). On ROCm, use upstream flash_attn.` The warm-up gate checks the config class, not the platform, although the model has an AMD attention path (`vllm/models/inkling/amd/attention.py`) |
| 5 | Add `--kernel-config '{"enable_jit_warmup": false}'` | **Engine ready** (`/health` 200); request 1 (DP rank 0) answered in 4.76 s; request 2, scheduled on DP rank 1 (the other node), produced **no output** and the engine died after 5 minutes | Every DP1 worker logged `No available shared memory broadcast block found in 60 seconds` five times → `TimeoutError: RPC call to sample_tokens timed out.` (`multiproc_executor.py:435`) → `EngineCore encountered a fatal error`; DP0 then died with `gloo … Connection closed by peer [<node1-private-ip>]`. During the hang GPU utilisation was 0 % on all 16 cards, no `hipcc`/`clang` process existed and the Triton cache gained no entry — not a JIT compile, a cross-node DP/EP collective that never completed |
| 6 | TP8 × PP2 (`--pipeline-parallel-size 2 --distributed-executor-backend ray`, one pipeline stage per node; no DP, no EP) | **Ready and generating**: all three requests returned; the `max_tokens=1024` request finished normally (`finish_reason=stop`) with a correct final answer | — (the Ray worker's first join hit a race with the head's GCS start-up, `GCS returned an authentication error`; restarting the worker container joined cleanly) |

Decisive log lines from attempt 5:

```text
Model loading took 114.88 GiB memory and 55.747657 seconds        # DP1; DP0 took 66.9 s
[aiter] [fused_moe] using 2stage default for ('gfx942', 304, 8, 6144, 3072, 16, 5, <ActivationType.Silu: 0>, 'torch.bfloat16', 'torch.bfloat16', 'torch.bfloat16', 'QuantType.No', True, False)
Available KV cache memory: 50.25 GiB
GPU KV cache size: 317,040 tokens, Maximum concurrency for 65,536 tokens per request: 4.84x   # per DP rank
Free memory on device (186.5/191.45 GiB) on startup … Actual usage is 117.4 GiB for consumed memory
init engine (profile, create kv cache, warmup model) took 76.77 s
WARNING [jit_monitor.py:141] Triton kernel JIT compilation during inference: _silu_and_mul_triton_kernel   # during request 1
INFO [shm_broadcast.py:801] No available shared memory broadcast block found in 60 seconds.               # during request 2, DP1, five times
TimeoutError: RPC call to sample_tokens timed out.
```

Attempt 5 smoke requests (`temperature=0`; originals in `evidence/inkling_bf16_16xMI300X/02_smoke_request.json` and `03_smoke2_request.json`):

| Request | Input | Output tokens (reasoning) | Wall clock | Content check |
|---|---|---:|---:|---|
| Chinese, "explain the difference between BF16 and FP16 in one sentence", `max_tokens=200` | 27 tokens | 200 (199), `finish_reason=length` | 4.76 s | Reasoning correct (BF16 8-bit exponent / 7-bit mantissa, FP16 5-bit exponent / 10-bit mantissa, range vs precision); reasoning did not finish within 200 tokens, so no final answer segment |
| English, three differences Mamba-2 vs softmax attention, `max_tokens=256` | 39 tokens | 0 | 600 s timeout | No output: scheduled on the remote DP rank, see attempt 5 above |

Decisive log lines from attempt 6 (TP8 × PP2):

```text
Using ['AITER_CUSTOM', 'PYNCCL'] all-reduce backends … for group 'tp:0'   /   Using ['PYNCCL'] … for group 'pp:0'
Using ROCm AITER Unquantized MoE backend out of potential backends: ['ROCm AITER', 'TRITON', 'BATCHED_TRITON']
Using MoEPrepareAndFinalizeNoDPEPModular
Using AiterExperts MoE backend
[aiter] [fused_moe] using 2stage default for ('gfx942', 304, 64, 6144, 384, 256, 6, <ActivationType.Silu: 0>, 'torch.bfloat16', 'torch.bfloat16', 'torch.bfloat16', 'QuantType.No', True, False)
Model loading took 109.52 GiB memory and 176.401031 seconds        # PP0 (node 0, first half of the layers); PP1: 116.12 GiB, 80.8 s
Available KV cache memory: 57.39 GiB                                # PP0; PP1: 51.02 GiB
GPU KV cache size: 398,239 tokens, Maximum concurrency for 65,536 tokens per request: 6.08x
Free memory on device (185.74/191.45 GiB) on startup … Actual usage is 112.54 GiB for consumed memory (weights + non-torch)   # PP0; PP1: 118.9 GiB
init engine (profile, create kv cache, warmup model) took 56.47 s
```

Attempt 6 smoke requests (`temperature=0`; originals in `evidence/inkling_bf16_16xMI300X_pp2/02_smoke_request.json`, `03_smoke2_request.json` and `07_smoke3_request.json`):

| Request | Input | Output tokens (reasoning) | Wall clock | Content check |
|---|---|---:|---:|---|
| Chinese, "explain the difference between BF16 and FP16 in one sentence", `max_tokens=200` | 27 tokens | 200 (199), `finish_reason=length` | 2.97 s | Reasoning correct; did not finish within 200 tokens |
| English, three differences Mamba-2 vs softmax attention, `max_tokens=256` | 39 tokens | 256 (255), `finish_reason=length` | 4.06 s | Reasoning correct: O(N²) vs O(N), pairwise QK + softmax vs state updates, Mamba-2's SSD; did not finish within 256 tokens |
| Same as the first, `max_tokens=1024` | 27 tokens | 441 (362), `finish_reason=stop` | 6.52 s | **Correct**: "BF16 keeps the same 8-bit exponent as FP32 (large dynamic range, hard to overflow) but only 7 mantissa bits (lower precision); FP16 has 10 mantissa bits (higher precision) but only 5 exponent bits (small range, prone to overflow or underflow)." (answer given in Chinese) |

Inkling is a reasoning model and its reasoning segment usually exceeds 200 tokens; the first two requests reused Nemotron's `max_tokens`, so they returned only reasoning. Raising the limit to 1024 produced the complete answer.

Weights per GPU: in the PP layout PP0 holds 109.52 GiB and PP1 116.12 GiB (each pipeline stage holds half the layers, TP8 within a stage, experts not sharded by EP); in the DP+EP layout each GPU holds 114.88 GiB. The [budget table](README.md#resource-estimate) gives 122 GB for EP16+TP8 (experts 1855.4 GB ÷ 16 + non-expert 49.3 GB ÷ 8); the difference comes from vLLM sharding some non-expert tensors over the EP group. The magnitude matches.

These results establish that the BF16 release loads on 16 × MI300X, is served by the AITER fused MoE kernel and answers correctly (TP8 × PP2 layout); the cross-node DP/EP layout did not complete the second request in this image, which this project records as the current state, not as a verdict on the model or the hardware. Evidence: [data/mi300x-run/inkling_bf16_16xMI300X_pp2/](data/mi300x-run/inkling_bf16_16xMI300X_pp2/) (attempt 6: three requests and responses, `rocm-smi` JSON, server-log key lines) and [data/mi300x-run/inkling_bf16_16xMI300X/](data/mi300x-run/inkling_bf16_16xMI300X/) (attempt 5: the first response, the timed-out second request, key lines). Full container logs, Ray worker logs from both nodes, the attempt 1–4 logs and the RCCL probe logs are in the author's private evidence directory with SHA-256 values in each directory's `SHA256SUMS.private.txt`; host names, private IPs and the login user are replaced by role labels in the public projection. The run scripts are in [scripts/mi300x/](scripts/mi300x/).

## Subsequent GPU validation

BF16 loading and smoke generation on MI300X are complete for Nemotron 3 Ultra and Inkling (above). Still unexecuted: ① Muse Spark Open BF16 — both Meta repositories are manually approved gated repositories; on 2026-11-02 a `config.json` read with this project's Hugging Face account returned 403 `GatedRepo` ("you are not in the authorized list"); the access request was submitted the same day, and after approval the same scripts run it on 2 nodes × 16 GPUs. ② The NVFP4 releases of all three models on MI300X — MI300X has no FP4 matrix arithmetic, the publishers' statements cover only Blackwell and Hopper, and whether vLLM ROCm rejects or dequantizes a ModelOpt NVFP4 checkpoint is unverified. ③ Throughput and latency, business-task quality and long-context stability remain unexecuted for all three models. Later measurements extend this project rather than creating a competing results page.