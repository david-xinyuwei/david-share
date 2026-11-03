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

The twenty-two tests: `inspect.test.mjs` (nine) covers three complete component tables with bilingual references/local links, independent repository prose, a layout guard (the five comparison tables in both READMEs — per-GPU budget, MI300X results, serving probe, reproduction steps and summary-first — keep their full column sets, and no code identifier is split by `<br>`, no empty `<code>` tag and no two-column stacked table appears; added after the 2026-11-02 layout regression), packed U8 accounting, the six observed payloads, retained Muse HTTP 401, Nemotron router exclusions, unknown dtypes, fresh revisions invalidating old configuration evidence, and HTTP failure without silently replaying old data. `census.test.mjs` (four) checks census-to-API byte parity, key component dtypes and tensor counts for both models, and rejection of unclassified components or a tampered total. `mi300x.test.mjs` (seven) checks that every number in `data/mi300x-run/summary.json` traces back to its raw request/response/log file, that the public projection contains no private identifiers, that the Nemotron and Inkling numbers quoted in all four documents equal the summary, that the run-2 serving-probe medians (TTFT, decode and aggregate tok/s at concurrency 1 and 8) quoted for each probed model appear on a table row with their unit exactly as recomputed from `08_perf.json`, that the documents claim no throughput/quality acceptance and describe the Muse pass only with the load/KV/token figures of the run in the summary, and that the parallel-layout figure (`images/mi300x-parallel-layout-{en,zh}.svg`) draws exactly the TP/PP/EP sizes and per-GPU weights/KV memory of the three run-2 layouts in the summary, embeds only the ledgered, unmodified Azure Virtual Machine icon, matches the SHA-256 in `data/visual-evidence.json`, and is embedded and captioned as original in both READMEs, and that the cross-node RCCL probe numbers quoted in all four documents (`nogdr` variant: 16 ranks, 64 MiB all_reduce 2.4 ms, 52.4 GB/s, exit 0; default-RDMA variant: watchdog timeout, exit 124) equal the `rccl_probe` entries of `summary.json`, which are read from the probe's own `RCCL_PROBE_OK` / `PROBE_EXIT` lines in `data/mi300x-run/rccl_probe/`. `mxfp4.test.mjs` (two) checks that every number in `data/mi300x-mxfp4/summary.json` traces back to its `launch.json`, `first_response.json`, `08_perf.json` and log key lines, that both passing deployments selected the `EMULATION` backend and the projection carries no private identifiers, that both READMEs quote the per-GPU weights, KV, first-answer token counts, TTFT and tok/s exactly and the text of Muse's two rejections, that the Muse MXFP4 cell in the summary-first table and the run-3 table says failed rather than passed, and that neither README has an NVFP4 result column or names the probe kernel (the probe is recorded only on this page). HTTP objects in tests are unit-test stubs, not live model evidence.

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
| Public identities and six pinned revisions | Read from the API; the three BF16 releases were downloaded in full on 2026-11-02 (Nemotron 3 Ultra 1,121,078,235,607 bytes, Inkling 1,904,787,107,666 bytes, Muse Spark Open 1,644,365,682,665 bytes after Meta approved the gate that morning); the other six were not downloaded |
| Original NVFP4 configuration | Nemotron and Inkling parsed; Muse returned 401 and was not parsed |
| Per-tensor dtype census | PASS for the two BF16 releases: 51,023 + 1,552 tensors read from safetensors headers; header byte totals equal the API metadata; no unclassified name pattern (see "Per-tensor dtype census") |
| File diagnostics | Editor checks executed; not evidence that Node tests passed |
| Node tests and CLI | PASS: twenty-one tests, zero failures (`node --test tests/inspect.test.mjs tests/census.test.mjs tests/mi300x.test.mjs tests/mxfp4.test.mjs`, re-run on every push by GitHub Actions `large-moe-precision-guide-ci.yml` on Ubuntu and Windows); three four-column tables with 25 items each, all nine releases, bilingual references/local links, six payload calculations, census-to-API byte parity, key component dtypes, every MI300X BF16 number quoted in the documents equal to `data/mi300x-run/summary.json`, and every run-3 MXFP4 number equal to `data/mi300x-mxfp4/summary.json` with the Muse failure recorded as failed in both READMEs |
| Table layout | PASS (2026-11-02/03, live GitHub pages): both READMEs show no page-level horizontal overflow at 1280 and 390 px; wide tables use GitHub's own in-table horizontal scrolling; the comparison tables keep their full column sets and no code identifier is split by `<br>` (the layout guard in `inspect.test.mjs` keeps checking this) |
| Full local preview | PASS: `tools/preview.ps1 -GitHubMarkdown` renders the four pages through the GitHub Markdown API with every image loaded; the live pages are authoritative |
| Cross-node RCCL probe, 2 × 8 MI300X (step 7) | PASS with `NCCL_NET_GDR_LEVEL=0`: 16-rank 64 MiB all_reduce 2.4 ms average, 52.4 GB/s bus bandwidth, `PROBE_EXIT=0` (2026-11-01 17:59Z); the default GPU Direct RDMA variant hit the 240 s collective watchdog and the 300 s script timeout (`PROBE_EXIT=124`); one message size, one run — a connectivity check, not a bandwidth benchmark; key lines in `data/mi300x-run/rccl_probe/` |
| MI300X BF16 load and smoke, Nemotron 3 Ultra | PASS on 8 × MI300X (attempt 3): engine ready, two requests answered correctly; kernels, cache precision and memory recorded in "MI300X run" |
| MI300X BF16 load and smoke, Inkling | PASS on 2 × 8 MI300X (attempt 6, TP8 × PP2): engine ready, three requests answered, the `max_tokens=1024` request gave a correct final answer; the TP8 × DP2 + EP16 layout (attempt 5) became ready and then hung on its second request, recorded as not passing in this image |
| MI300X BF16 load and smoke, Muse Spark Open | PASS on 2 × 8 MI300X (attempt 3, TP8 × PP2, `vllm/vllm-openai-rocm:v0.33.0` + Ray): engine ready in 4 min 36 s, four requests answered, the `max_tokens=4096` request gave a correct final answer after 1,289 reasoning tokens; attempts 1 (no Ray in the recipe image) and 2 (recipe image compiled for `gfx950` only → segfault in the fused qk-norm/rope/kv-insert kernel) recorded in "Run 2" |
| Serving-speed probe (TTFT, tok/s at concurrency 1 and 8) | PASS (run 2): one `09_perf_probe.py` run each for Inkling TP8×PP2, Nemotron TP8+EP and Muse TP8×PP2 (one short prompt, max_tokens 256, 3 rounds per level); numbers in "Run 2"; an order-of-magnitude probe, not a benchmark |
| MXFP4 emulation path on MI300X, Inkling | PASS on 8 × MI300X (run 3, TP8, `lightseekorg/Inkling-MXFP4` Quark checkpoint, `EMULATION` backend): 66.74 GiB weights per GPU, correct final answer, probe 6.1 tok/s per request at concurrency 1; recorded in "Run 3" |
| MXFP4 emulation path on MI300X, Nemotron 3 Ultra | PASS on 8 × MI300X (run 3, TP8 + EP8, BF16 checkpoint quantized online with vLLM's official `--quantization online` flags, `EMULATION` backend): 43.21 GiB weights per GPU, correct final answer, probe 7.7 tok/s per request at concurrency 1; recorded in "Run 3" |
| MXFP4 emulation path on MI300X, Muse Spark Open | FAIL (run 3, two attempts): the generic online entry is refused (`got quantization 'online'`), and Muse's own entry enters MXFP4 but the model code refuses the `EMULATION` backend (`requires the AITER_MXFP4_MXFP4 backend`); no weights loaded; recorded in "Run 3" |
| Throughput distribution, long prompts, business-task quality, MXFP4-versus-BF16 quality regression, long context, production stability | NOT_RUN for all three models |
| NVFP4 releases: full-model load on MI300X | NOT_RUN; only the single-expert kernel probe was run for Nemotron and Inkling (relative L2 error 0 and 3.74×10⁻⁹ against the PyTorch reference, 1 GPU, `Nvfp4QuantizationEmulationTritonExperts`); Muse's NVFP4 config returns 401 |
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

These results establish that the BF16 release loads on 16 × MI300X, is served by the AITER fused MoE kernel and answers correctly (TP8 × PP2 layout); the cross-node DP/EP layout did not complete the second request in this image, which this project records as the current state, not as a verdict on the model or the hardware. Evidence: [data/mi300x-run/inkling_bf16_16xMI300X_pp2/](data/mi300x-run/inkling_bf16_16xMI300X_pp2/) (attempt 6: three requests and responses, `rocm-smi` JSON, server-log key lines) and [data/mi300x-run/inkling_bf16_16xMI300X/](data/mi300x-run/inkling_bf16_16xMI300X/) (attempt 5: the first response, the timed-out second request, key lines). Full container logs, Ray worker logs from both nodes and the attempt 1–4 logs are in the author's private evidence directory with SHA-256 values in each directory's `SHA256SUMS.private.txt`; host names, private IPs and the login user are replaced by role labels in the public projection. The two RCCL probe runs (`07_rccl_probe.sh`, 2026-11-01 17:54Z default GPU Direct RDMA → watchdog timeout after 240 s, `PROBE_EXIT=124`; 17:59Z `NCCL_NET_GDR_LEVEL=0` → `RCCL_PROBE_OK=True world=16`, 64 MiB all_reduce 2.4 ms, 52.4 GB/s, `PROBE_EXIT=0`) are projected as key lines in [data/mi300x-run/rccl_probe/](data/mi300x-run/rccl_probe/), with the full logs hashed in that directory's `SHA256SUMS.private.txt`; `summary.json` carries their numbers under `rccl_probe`. The run scripts are in [scripts/mi300x/](scripts/mi300x/).

### Run 2 (2026-11-02 morning): re-run + serving-speed probe + Muse

<a id="run-2"></a>

The two VMs were deallocated at 03:05 and started again at 10:06 (local NVMe is ephemeral, so weights and images were downloaded again: 4.67 TB for the three models in 17 minutes across the two nodes, byte counts identical to run 1). Run 2 had two purposes: a **serving-speed probe** on each layout that passed in run 1, and the first Muse attempt after Meta approved the weight gate.

**Probe method** ([`scripts/mi300x/09_perf_probe.py`](scripts/mi300x/09_perf_probe.py), stdlib only, run on node 0's host against `127.0.0.1:8000`): one fixed English prompt, "Explain in about 150 words why mixture-of-experts models keep the router in higher precision than the experts." (37 tokens), `max_tokens 256`, `temperature 0`, `stream: true` with `stream_options.include_usage: true`; one warm-up request, then 3 rounds at concurrency 1 and 3 rounds at concurrency 8, each round issuing all its requests from threads at once. Definitions: TTFT = send to the first chunk carrying `content` or `reasoning_content`; decode speed per request = (completion_tokens − 1) ÷ (last chunk − first chunk); aggregate = sum of completion_tokens over a round's streams ÷ (last finish − first send). `completion_tokens` comes from the server's final `usage` chunk. `rocm-smi --showmeminfo vram` is recorded before and after. This is an order-of-magnitude probe — one short prompt, two concurrency levels, three rounds each; it is not a benchmark and does not replace a business-load test.

| Model · layout (run 2) | Ready | Smoke (same three requests as run 1) | Concurrency 1 (n=3): TTFT median / decode per request / aggregate | Concurrency 8 (n=24): TTFT median / decode per request / aggregate | Finish reasons |
|---|---|---|---|---|---|
| Inkling BF16 · TP8×PP2 · 0.29 image | 03:46:25Z (head started 03:39:08Z; cold load 249.6 / 243.7 s; `init engine` 58.22 s; KV 57.39 / 51.02 GiB, 398,239 tokens — identical to run 1) | 3/3 returned: 3.01 s / 4.10 s / 5.57 s; the `max_tokens=1024` request gave 377 tokens (302 reasoning), `finish_reason=stop`, correct answer | **0.045 s** / **68.9 tok/s** / 68.3 tok/s | **0.097 s** (max 0.102) / **42.5 tok/s** / **335.8 tok/s** | all 27 `length` (reasoning segment not finished within 256 tokens) |
| Nemotron 3 Ultra BF16 · TP8+EP · 0.29 image | 04:05:02Z (started 03:49:28Z; cold load 744.5 s, slower than run 1's 443 s because the page cache was full of Inkling after the three parallel downloads; `init engine` 117.78 s; KV 23.07 GiB, 3,490,022 tokens — identical to run 1) | 3/3 `stop`: 1.61 s / 5.39 s / 1.60 s; the Chinese answer is identical to run 1 (94 tokens, 21 reasoning) | **0.170 s** / **60.7 tok/s** / 58.6 tok/s | **0.358 s** (max 1.17) / **42.0 tok/s** / **317.4 tok/s** | all 27 `length` (the 256-token cap came first; the answer segment had started) |
| Muse Spark Open BF16 · TP8×PP2 · v0.33.0+Ray image (attempt 3) | 04:22:41Z (head started 04:18:05Z; `Model loading took 99.1 GiB memory` on all 16 ranks, 95.0 s on stage 0 and 39.6–43.1 s on stage 1; `init engine` 64.22 s; `Available KV cache memory` 72.05 / 71.98 GiB, `GPU KV cache size: 8,130,184 tokens`) | 3/3 returned: 6.69 s / 4.33 s / 12.41 s, all `finish_reason=length` inside the reasoning segment (200 / 256 / 1024 tokens); a fourth request, the same Chinese prompt with `max_tokens=4096`, ended `stop` after 1,354 completion tokens (1,289 reasoning; no wall time was recorded for this added request, `wall_secs` is null in `summary.json`) with the correct one-sentence answer (BF16 = 8 exponent + 7 mantissa bits, FP32's range at lower precision; FP16 = 5 + 10, higher precision but overflows easily) | **0.205 s** / **84.6 tok/s** / 79.5 tok/s | **0.506 s** (max 0.518) / **47.6 tok/s** / **348.6 tok/s** | all 27 `length` (reasoning segment not finished within 256 tokens) |

Inkling's run-2 load and KV figures match run-1 attempt 6 to the digit (`Model loading took 109.52 / 116.12 GiB`, `Available KV cache memory 57.39 / 51.02 GiB`, `GPU KV cache size 398,239 tokens`), so the memory footprint of this layout is deterministic; the smoke wall clocks 3.01 / 4.10 / 5.57 s are in the same range as run 1's 2.97 / 4.06 / 6.52 s. During the probe `rocm-smi` showed 170.6–171.2 GiB in use per GPU on node 0 and 177.2–177.9 GiB on node 1 (weights + KV pre-allocation + runtime), unchanged before and after. Evidence: [data/mi300x-run/inkling_bf16_16xMI300X_pp2_run2/](data/mi300x-run/inkling_bf16_16xMI300X_pp2_run2/) including `08_perf.json` with all 28 per-request records.

**Muse Spark Open BF16, three attempts** (weight gate approved on the morning of 2026-11-02; `meta-models/Muse-Spark-Open-816B-A42B` revision `0fb02478…`, 1,644,365,682,665 bytes, one copy per node; config: 62 layers, hidden 8192, 256 experts top-8, 128 Q heads / 16 KV heads / head_dim 64, vocabulary 202,048; 1.64 TB ÷ 8 = 205 GB does not fit one node, so the two-node TP8 × PP2 layout that passed for Inkling was reused):

| Attempt | Image | Result | Root cause in the log |
|---|---|---|---|
| 1 | `vllm/vllm-openai-rocm:muse-spark-open` (the vLLM recipe image, vLLM 0.29.1rc1, pushed 2026-10-15) | Failed within one second | worker: `/bin/bash: line 1: ray: command not found`; head: `pydantic ValidationError for ParallelConfig: Failed to import Ray: No module named 'ray'` — the image has no Ray, and vLLM's multi-node executor needs Ray ≥ 2.43.0 (`vllm/v1/executor/ray_executor.py`). The recipe is single-node TP8 on MI355X (288 GB) and never needs it |
| 2 | Same image + `ray[default]==2.55.1` ([`Dockerfile.muse-ray`](scripts/mi300x/Dockerfile.muse-ray), `BASE=muse-spark-open`) | Ray cluster of 16 GPUs formed; **all 16 ranks loaded the weights** (`Model loading took 104.84 GiB memory and 189.7 seconds`, `Materialized residual-path constants for 62 gated residual connections`); then **every rank segfaulted** in `determine_available_memory`: `RayWorkerProc rank=[15] died unexpectedly` → `Engine core initialization failed` | Each worker's `.err` reads `!!!!!!! Segfault encountered !!!!!!!` at `csrc/libtorch_stable/fused_muse_spark_qknorm_rope_kv_insert_kernel.hip:647/821` (`launchFusedMuseSparkTyped<BFloat16,…>`); node 1 `dmesg`: `amdgpu: Freeing queue vital buffer … queue evicted` ×7. The image has `PYTORCH_ROCM_ARCH=gfx950`; `llvm-objdump --offloading` shows all 28 code objects in `_C_stable_libtorch.abi3.so` (which carries that kernel) are `gfx950`, and `_C.abi3.so` / `_rocm_C.abi3.so` likewise `gfx950` only; the host's `rocminfo` is `gfx942`. **No code object for MI300X**, so launching the kernel faults. The fused path is selected unconditionally for ROCM_AITER_FA + BF16 + head_dim 64 (`models/muse_spark/amd/model.py:535`) and has no environment switch |
| 3 | `vllm/vllm-openai-rocm:v0.33.0` (released 2026-11-02 02:45 UTC: vLLM 0.33.0, torch 2.13.0+rocm10.0.0, `PYTORCH_ROCM_ARCH=gfx90a;gfx942;gfx950;gfx11xx;gfx12xx`, the same `vllm/models/muse_spark/` tree, `_C_stable_libtorch.abi3.so` with 28 code objects per architecture including `fused_muse_spark_qknorm_rope_kv_insert`) + `ray[default]==2.55.1` | **Passed**: Ray cluster formed in 33 s, weights loaded, memory profiling ran through the same fused kernel without fault, `/health` 200 at 04:22:41Z, four requests answered, probe completed (table above) | Log: `Using MuseSparkTritonExperts MoE backend`, `Using ROCM_AITER_FA backend (selected via --attention-backend)`, all-reduce `['AITER_CUSTOM', 'PYNCCL']` for `tp:0` and `['PYNCCL']` for `pp:0`, `Enabled custom fusions: norm_quant, act_quant, allreduce_rms, mla_dual_rms_norm, qk_norm_rope_kvcache`; `vllm 0.33.0+rocm100`, `ray 2.55.1` inside the container. The only change from attempt 2 is the base image, so the attempt-2 failure is attributed to the missing `gfx942` code objects, not to the model or the layout |

Attempt-2 evidence: node 0 `attempt2_head_full.log`, `attempt2_image_code_objects.txt` (the `llvm-objdump` output), `host_gfx_arch.txt`; node 1 the eight Ray `worker-*.err` files (segfault stacks), `raylet.err`, `dmesg_amdgpu_tail.txt` — in the author's private evidence directory, SHA-256 listed in `SHA256SUMS.private.txt`. The image inspection and the segfault stacks prove that **this image was not compiled for gfx942**, not anything about the model or MI300X; the v0.33.0 code-object list shows upstream now compiles gfx942, which is why attempt 3 used it. Attempt-3 evidence: [data/mi300x-run/muse_bf16_16xMI300X_pp2_run2/](data/mi300x-run/muse_bf16_16xMI300X_pp2_run2/) (server key lines, the four request/response pairs, `rocm-smi` snapshot, `08_perf.json` with all 28 per-request records). During the probe `rocm-smi` showed 180.0–180.9 GiB in use per GPU on node 0 and 180.3–181.4 GiB on node 1 (99.1 GiB weights + ~72 GiB KV pre-allocation + runtime); Muse's KV pool is the largest of the three because its 16 KV heads × head_dim 64 give the smallest KV footprint per token (8.13 M tokens against Inkling's 398 K and Nemotron's 3.49 M at the same 32,768 `max_model_len`).

### Run 3 (2026-11-02, 07:49–09:29 UTC): MXFP4 emulation path and the NVFP4 single-expert probe

<a id="run-3"></a>

All of run 3 used node 0 alone (8 × MI300X) and the `vllm-muse-ray:0.33.0` image already built for Muse (vLLM 0.33.0+rocm100, torch 2.13.0+rocm10.0.0, Triton 3.8.0; image ID `1bf04962…` on node 0, `8cfe951c…` for the same tag on node 1). The question is narrow: MI300X has no FP4 matrix arithmetic, so what happens when the three models' 4-bit weights are offered to vLLM on this GPU? The acceptance script ([`12_mxfp4_acceptance.py`](data/mi300x-mxfp4/nemotron_mxfp4_8xMI300X/SHA256SUMS.private.txt), hashed in each run's private list) starts the container, follows the log until `Application startup complete`, sends one Chinese request identical to the BF16 smoke test but with `max_tokens 4096` so that a final answer is reached, then runs the unchanged run-2 [`09_perf_probe.py`](scripts/mi300x/09_perf_probe.py). Every run used `--enforce-eager`, `max_model_len 32768`, `gpu_memory_utilization 0.90`.

**NVFP4 single-expert probe (07:49Z, 1 GPU).** Before touching full models, [`11_fp4_compat_probe.py`](data/mi300x-mxfp4/nvfp4_single_expert_probe_1xMI300X/SHA256SUMS.private.txt) fetched expert 0's real NVFP4 weights and scales from the Nemotron (`02462641`) and Inkling (`42a75a99`) NVFP4 checkpoints by HTTP range request, ran one expert forward on two deterministic synthetic activation rows with a fixed top-1 route through vLLM's `Nvfp4QuantizationEmulationTritonExperts`, and compared with a PyTorch reference that shares vLLM's activation quantize-dequantize step: relative L2 error 0 (Nemotron) and 3.74×10⁻⁹ (Inkling), both finite and non-zero. This establishes only that the two checkpoints' expert tensor layout is read correctly by the emulated kernel on gfx942. It is not model loading, generation, quality or throughput. Muse's NVFP4 config still returned 401, so it was not probed. Evidence: [data/mi300x-mxfp4/nvfp4_single_expert_probe_1xMI300X/gpu_probe.json](data/mi300x-mxfp4/nvfp4_single_expert_probe_1xMI300X/gpu_probe.json).

**Full-model MXFP4 (08:20–08:52Z).** vLLM selected the `EMULATION` MXFP4 backend on MI300X in both runs (`Using 'EMULATION' Mxfp4 MoE backend`, `Using OCP_MXQuantizationEmulationTritonExperts`, with the engine's own warning that it "will dequantize weights on the fly and may be slower than native quantized MOE"):

| Model · entry point | Launch (actual argv in `launch.json`) | Load | First answer (`max_tokens 4096`) | Probe: concurrency 1 (n=3) → TTFT / decode tok/s | Probe: concurrency 8 (n=24) → TTFT / decode tok/s / aggregate tok/s |
|---|---|---|---|---|---|
| Inkling · Quark checkpoint `lightseekorg/Inkling-MXFP4` revision `bc3fdef2…` (`w_mxfp4_a_mxfp4`, the MI300X emulation path the vLLM recipe lists [I3]) | `--quantization` inferred as `quark` from the checkpoint; `--moe-backend auto`, TP8, `--tokenizer-mode inkling --reasoning-parser inkling` | `Model loading took 66.74 GiB memory and 348.4 s`; `Available KV cache memory: 94.79 GiB`; `GPU KV cache size: 305,150 tokens` | `finish_reason=stop`, 413 completion tokens (354 reasoning), TTFT 8.71 s, first final-answer text at 69.58 s, wall 78.56 s; answer correct (BF16 8-bit exponent / 7-bit mantissa, FP16 5 / 10) | 0.358 s / 6.1 tok/s | 0.726 s (max 3.53) / 5.7 tok/s / 44.6 tok/s |
| Nemotron 3 Ultra · BF16 checkpoint `77df655d…` quantized online | `--quantization online --quantization-config '{"moe":"mxfp4"}' --moe-backend emulation`, TP8 + EP8, `--mamba-ssm-cache-dtype float16`, `--reasoning-parser nemotron_v3` | `Online quantization as part of model loading took 1.2–1.8 s` per rank; `Model loading took 43.21 GiB memory and 396.7 s`; `Available KV cache memory: 111.86 GiB`; `GPU KV cache size: 13,758,836 tokens` | `finish_reason=stop`, 110 completion tokens (21 reasoning), TTFT 6.21 s, first final-answer text at 11.44 s, wall 22.64 s; answer correct (its remark about loss scaling concerns mixed-precision training, not an inference requirement) | 0.178 s / 7.7 tok/s | 0.484 s (max 1.33) / 6.9 tok/s / 54.9 tok/s |

All 27 probe requests per model ended with `finish_reason=length` (256-token cap inside the reasoning segment), as in run 2. `rocm-smi` before the probe showed 178.9–179.5 GiB in use per GPU for Inkling and 174.8–175.2 GiB for Nemotron (weights + the 0.90 KV pre-allocation + runtime). Compared with the BF16 runs the saving is memory (Nemotron 136.51 → 43.21 GiB per GPU; Inkling 16 GPUs → 8), not speed: decode is 6–8 tok/s against 60–85 for BF16 — but the BF16 runs used the 0.29.0 image without eager mode and Inkling BF16 had 16 GPUs, so the gap is not attributed to quantization alone. Evidence: [data/mi300x-mxfp4/inkling_mxfp4_8xMI300X/](data/mi300x-mxfp4/inkling_mxfp4_8xMI300X/) and [data/mi300x-mxfp4/nemotron_mxfp4_8xMI300X/](data/mi300x-mxfp4/nemotron_mxfp4_8xMI300X/) (actual argv, first response with reasoning text, `08_perf.json` with all 28 per-request records, server key lines); full server and acceptance logs stay private with their SHA-256 in `SHA256SUMS.private.txt`.

**Muse Spark Open MXFP4, two attempts (09:24–09:29Z), both failed before loading weights.** Source checkpoint is the BF16 original (`0fb02478…`, already on both nodes), TP8 on node 1:

| Attempt | Flags | What the log shows | Classification |
|---|---|---|---|
| 1 | Nemotron's generic flags: `--quantization online --quantization-config '{"moe":"mxfp4"}' --moe-backend emulation` | All 8 workers: `NotImplementedError: MuseSpark1x on ROCm only supports Quark W8A8 FP8 or OCP-MXFP4 W4A4 quantized checkpoints; got quantization 'online'.` Exit code 1 within 70 s | Wrong entry point: Muse's ROCm model code does not accept the generic online-quantization path |
| 2 | Muse's own entry: environment `VLLM_ROCM_MUSE_MOE_ONLINE_QUANT=mxfp4`, `--moe-backend auto`, no generic quantization flags | `Using 'EMULATION' Mxfp4 MoE backend`, then all 8 workers: `NotImplementedError: MuseSpark1x MXFP4 on ROCm requires the AITER_MXFP4_MXFP4 backend; got EMULATION.` Exit code 1 within 80 s | Explicit rejection in `vllm/models/muse_spark/amd/`: Muse's experts need a per-route post-norm before the weighted reduction, which only AITER's native MXFP4 kernel (MI350 series) implements; the emulation backend is refused by design |

No OOM, no segfault, no weights loaded, no answer and no probe. The conclusion is "this vLLM version's Muse code does not run MXFP4 on gfx942", not a statement about Muse's weights or about MI300X memory. Pre-quantized checkpoints `amd/Muse-Spark-Open-816B-A42B-Quark-MXFP4` and `intel-ai/Muse-Spark-Open-816B-A42B-MXFP4` exist on Hugging Face; neither was tested, and their existence is not MI300X compatibility evidence. Evidence: [data/mi300x-mxfp4/muse_mxfp4_8xMI300X_attempt1_generic_online_flags/](data/mi300x-mxfp4/muse_mxfp4_8xMI300X_attempt1_generic_online_flags/) and […attempt2_muse_online_quant_env/](data/mi300x-mxfp4/muse_mxfp4_8xMI300X_attempt2_muse_online_quant_env/) (actual argv, acceptance state, error lines). The BF16 Muse service on both nodes and the Nemotron MXFP4 service on node 0 were left running after run 3; no VM was shut down.

## Subsequent GPU validation

On MI300X the BF16 load, smoke and serving-speed probe are complete for all three models (Nemotron 3 Ultra and Inkling on the 0.29.0 image; Muse Spark Open on the v0.33.0 image), and the MXFP4 emulation path is complete for Inkling and Nemotron and recorded as rejected by the model code for Muse. Still unexecuted: ① Muse's multimodal path (`--language-model-only` was used, so the vision encoder was never loaded) and a re-run of Inkling and Nemotron BF16 on the same v0.33.0 image, which is what a controlled cross-model or BF16-versus-MXFP4 comparison would need. ② Full-model loading of the three original NVFP4 releases on MI300X — only the Nemotron and Inkling single-expert kernel probes were run, and Muse's NVFP4 config still returns 401. ③ Quality regression of the MXFP4 deployments against BF16 on real tasks, throughput distributions, long prompts and long-context stability (32K was configured, not tested with a 32K input) remain unexecuted for all models — the probes give only the order of magnitude for one short prompt at two concurrency levels. Later measurements extend this project rather than creating a competing results page.