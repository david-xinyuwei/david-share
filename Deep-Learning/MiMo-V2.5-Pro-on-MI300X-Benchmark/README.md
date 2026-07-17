# MiMo-V2.5-Pro on AMD MI300X — Benchmark Report

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

Running **Xiaomi MiMo-V2.5-Pro (1.02T MoE / 42B active / FP8)** on Azure **AMD Instinct MI300X** with SGLang + AMD CK A8W8 blockwise GEMM + AITER + MTP/EAGLE + model-specific fused-MoE tuning, shown alongside Xiaomi's H200 reference data.

This customer-facing repo contains the headline comparison, the complete Microsoft-run scalability extension, one supported reproduction bundle, and compact runtime metadata. For PD-separated decode, the container must expose RDMA devices (`--privileged`, `/dev/mem`, and `CAP_SYS_ADMIN`); otherwise Mooncake falls back to TCP and high-concurrency throughput results are invalid.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)
>
> Last tested: 2026-07-17

English | [中文版](README-CN.md) | [Validation Evidence](data/validation/)

> **64K Decode highlight (one measurement run per point):** on the final two-node 1P1D MI300X runtime, mean TPOT stays at 11.55–11.94 ms from concurrency 16 to 96. Against the customer-provided H200 per-DP TPOT at matching local batch, MI300X is at parity at 16 and has **17.8–41.1% lower TPOT** at 32–96. This is a directional Decode-only observation. It does not claim Prefill or E2E leadership: MI300X reaches 69.3% of the customer H200 64K per-node Prefill reference, and the customer source has no matching 64K E2E result.

---

## Architecture

![Two-node MI300X 1P1D Prefill-Decode architecture](images/pd_architecture.png)

*Figure 1. Final two-node MI300X 1P1D topology, Mooncake KV transfer path, and validated runtime stack.*

---

## Headline Results — Microsoft-Tested MI300X vs Xiaomi H200

The tables below contain selected, validated customer-comparison points from accepted runs. Each MI300X row keeps metrics from one measurement record; the next section separately reports one complete scalability matrix.

### 1P1D Prefill

| Context | Concurrency | Microsoft-tested MI300X input tok/s | Xiaomi H200 TP8/EP16/DP2 per-node reference | MI300X / H200 per node |
|---:|---:|---:|---:|---:|
| 8K | 4 | **20,305.98** | 31,950 | 63.6% |
| 64K | 4 | **18,983.91** | 27,400 | 69.3% |
| 256K | 4 | **12,864.96** | 17,400 | 73.9% |

### 1P1D Decode — 8K Input / 1K Output

| MI300X concurrency | H200 per-DP BS | Microsoft-tested MI300X output tok/s | Xiaomi H200 reported per-DP/per-node tok/s | MI300X / H200 per node |
|---:|---:|---:|---:|---:|
| 16 | 16 | **1,331.98** | 1,381 | 96.5% |
| 32 | 32 | **1,936.24** | 2,549 | 76.0% |
| 64 | 64 | **2,465.01** | 4,483 | 55.0% |
| 128 | 128 | **2,486.89** | 7,013 | 35.5% |

#### Decode TPOT — Lower Is Better

| MI300X concurrency | H200 per-DP BS | Microsoft-tested MI300X mean TPOT (ms) | Xiaomi H200 TPOT reference (ms) | MI300X / H200 |
|---:|---:|---:|---:|---:|
| 16 | 16 | **10.83** | 11.59 | 0.93× |
| 32 | 32 | **13.65** | 12.56 | 1.09× |
| 64 | 64 | **16.88** | 14.28 | 1.18× |
| 128 | 128 | **16.56** | 18.25 | 0.91× |

A ratio below 1.00× means lower TPOT on MI300X. These rows compare one MI300X decode node with one H200 DP replica/node at the same local batch size. The H200 report uses DP=4, so this is not a whole-deployment aggregate comparison. Each MI300X TPOT is paired with the same measurement record as the throughput directly above.

### Two-Node DP=2 Prefill — Peak Aggregate Throughput

| Context | Concurrency | Aggregate input tok/s |
|---:|---:|---:|
| 8K | 16 | **46,747.01** |
| 64K | 2 | **38,984.45** |

The nominal-length 256K DP=2 observation is retained in the detailed scalability matrix, but it is not an exact-token headline result.

### Result Scope

- Headline values come from multiple accepted reproduction runs selected for final configuration and validity, not one single matrix or an across-run aggregate. The `headline_source` field in the machine-readable data records the source run; the detailed scalability table is the complete-matrix view, and the repeatability table shows run-to-run variation.
- The headline 1P1D 256K result sends exactly 262,144 token IDs per request with `--tokenize-prompt`.
- DP=2 values are aggregate Prefill-only capacity across two MI300X nodes; they do not include P→D KV-cache transfer.
- The H200 Decode `tok/s` values are the report's per-DP/per-node-style values (`BS × TPS`); they are not presented as DP=4 aggregate throughput.
- H200 figures remain directional references, not a strict apples-to-apples hardware benchmark: MI300X uses real expert routing, while the H200 reference uses idealized balanced routing.
- Machine-readable headline results: [`data/final-results.tsv`](data/final-results.tsv).

### H200 Reference Provenance

| Field | Public record |
|---|---|
| Source | Xiaomi-provided MiMo-V2.5-Pro performance report, privately archived and not redistributed |
| Reviewed | 2026-05-18 |
| Prefill reference | TP8/EP16/DP2, balanced `fake_topk_ids`, radix cache disabled, single-machine/per-node throughput |
| Decode reference | 8K and 64K input / 1K output; TP8/EP32/DP4, balanced `fake_topk_ids`, MTP layer 3, reported accept rate 0.75 |
| Decode TPOT origin | Customer worksheet; derived from per-DP Decode log output rate and local BS as `1000 / (tok/s ÷ BS)` |
| Decode throughput scope | Reported per-DP/per-node-style `BS × TPS`; not confirmed as DP=4 aggregate throughput |
| Delivery use | Directional per-node/per-DP reference only |

Machine-readable provenance and all reference values are in [`data/validation/h200-reference.json`](data/validation/h200-reference.json).

---

## Microsoft Scalability Extension

AMD provided the base launch method: the container image, tuned AITER path, 1P1D/DP=2 topology, and benchmark entry points. Microsoft first reproduced that path, then independently extended the context and concurrency coverage and added fail-closed correctness gates. **Every MI300X performance value below is Microsoft-measured; the H200 TPOT values are customer-provided references recorded in `h200-reference.json`. No AMD performance values are included.**

### Test Matrix

| Surface | Workload | Concurrency sweep | Requests per point |
|---|---|---|---:|
| 1P1D Decode | 8K input / 1K output | 8, 16, 32, 64, 96, 128, 192 | 256 |
| 1P1D long-context Decode | Requested 64K input / 1K output; requested 255K input / 1K output (256K total sequence) | 64K: 16, 32, 64, 96; 255K: 1 | 32, 64, 128, 192; 1 |
| 1P1D Prefill | 8K, 64K, nominal 256K / 1 output | 1, 2, 4, 8 | 16 |
| Two-node DP=2 Prefill | 8K, 64K, nominal 256K / 1 output | 8K/64K: 1, 2, 4, 8, 16; nominal 256K: 1, 2, 4, 8 | 32 |

The tables below present the measured scalability results. The core Decode production points were separately repeated on fresh services.

### Decode Scalability — 8K Input / 1K Output

| Concurrency | Output tok/s | Mean TPOT (ms) | Mean TTFT (ms) |
|---:|---:|---:|---:|
| 8 | 930.00 | 7.65 | 863.69 |
| 16 | 1,303.44 | 10.72 | 1,398.73 |
| 32 | 1,930.10 | 13.68 | 2,296.89 |
| 64 | 2,462.83 | 17.08 | 7,406.18 |
| 96 | 2,497.69 | 15.89 | 18,273.38 |
| 128 | 2,468.95 | 16.45 | 27,128.38 |
| 192 | 2,500.54 | 15.98 | 40,956.57 |

Observed behavior:

- Throughput increased from 930.00 tok/s at concurrency 8 to 2,462.83 tok/s at concurrency 64, then plateaued around 2.47–2.50K tok/s through concurrency 192.
- TTFT increased sharply after concurrency 64 even while throughput stayed flat. The plateau is therefore a capacity result, not a latency improvement.

### Core Decode Fresh-Service Repeatability

| Concurrency | Fresh run 1 tok/s | Fresh run 2 tok/s | Throughput delta | TPOT run 1 / run 2 (ms) |
|---:|---:|---:|---:|---:|
| 16 | 1,331.98 | 1,303.44 | -2.14% | 10.83 / 10.72 |
| 32 | 1,936.24 | 1,930.10 | -0.32% | 13.65 / 13.68 |
| 64 | 2,457.73 | 2,462.83 | +0.21% | 17.00 / 17.08 |
| 128 | 2,486.89 | 2,468.95 | -0.72% | 16.56 / 16.45 |

The maximum absolute two-run throughput delta was **2.14%** across the four repeated points.

### Long-Context Decode — Final Baked Image

These points were measured on 2026-07-17 by pulling and running the immutable image listed in the Software Stack section. Each row is one measurement run; multiple requests within a row are not independent repetitions.

Long ISL primarily stresses **Prefill**. Use Input tok/s and TTFT to judge long-ISL ingestion and online responsiveness. Use TPOT/ITL at fixed local batch to judge Decode after the first token. Throughput is measured in tokens/s; `TPUT` is shorthand for throughput, not a separate metric.

| Metric | Dominant phase | Interpretation |
|---|---|---|
| Input tok/s | Prefill | Primary long-ISL capacity metric; higher is better |
| TTFT | Prefill + queueing + KV transfer | Time until the first generated token; lower is better |
| TPOT / ITL | Decode | Per-output-token latency after the first token; lower is better |
| Decode server output tok/s | Decode | Decode-side capacity at a fixed workload; higher is better |
| SGLang E2E Output token throughput | Full request | Includes Prefill/TTFT; do not treat as pure Decode capacity |

#### Decode-Side Advantage — 64K Input / 1K Output

| Local concurrency / per-DP BS | MI300X mean TPOT (ms) | Xiaomi H200 mean TPOT (ms) | MI300X / H200 |
|---:|---:|---:|---:|
| 16 | 11.94 | 11.99 | 1.00× |
| 32 | 11.76 | 14.31 | 0.82× |
| 64 | 11.75 | 16.33 | 0.72× |
| 96 | 11.55 | 19.63 | 0.59× |

At matching local batch, MI300X is effectively at parity at 16 and has **17.8–41.1% lower TPOT** at 32–96. Lower TPOT means faster per-request token generation after the first token.

H200 TPOT is a customer-worksheet value derived from per-DP Decode log throughput. This is a directional same-workload, same-local-batch Decode view, not a whole-deployment comparison: MI300X uses real expert routing, while the H200 reference uses balanced `fake_topk_ids`, TP8/EP32/DP4, MTP3, and reported accept rate 0.75.

H200 source: customer-provided report reviewed 2026-05-18 and revalidated against the source workbook on 2026-07-17; see [`data/validation/h200-reference.json`](data/validation/h200-reference.json). The private workbook is not redistributed.

#### What Can and Cannot Be Compared to H200

| Surface | Microsoft-tested MI300X | Customer-provided H200 | Decision |
|---|---:|---:|---|
| 64K Prefill | 18,983.91 input tok/s | 27,400 input tok/s | Directional per-node comparison: MI300X is 69.3% of H200; no MI300X lead |
| 64K Decode | 11.55–11.94 ms TPOT | 11.99–19.63 ms TPOT at matching BS | Directional same-local-batch comparison: MI300X leads at BS32–96 |
| 64K/1K E2E | Measured output-equivalent tok/s and TTFT | No matching customer E2E result | No H200 ratio or parity claim |
| Requested 255K + 1K | One successful capability point | No exact matching customer workload | Capability only; no H200 comparison |

#### End-to-End 1P1D Diagnostic — Prefill-Inclusive

SGLang's `Output token throughput` is an **end-to-end (E2E)** metric: total requested output tokens divided by full benchmark duration, including Prefill/TTFT. It is not pure Decode-server capacity. For this fixed 64K/1K workload, the reported `Output token throughput = Input token throughput ÷ 64` by construction.

| Requested ISL | OSL | Concurrency | Requests | SGLang E2E output tok/s (Prefill-inclusive) | Input tok/s | Mean TPOT (ms) | Mean TTFT (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| Requested 64K | 1K | 16 | 32 | 265.17 | 16,970.68 | 11.94 | 37,571.24 |
| Requested 64K | 1K | 32 | 64 | 276.59 | 17,701.98 | 11.76 | 80,228.37 |
| Requested 64K | 1K | 64 | 128 | 284.00 | 18,175.89 | 11.75 | 165,190.68 |
| Requested 64K | 1K | 96 | 192 | 288.66 | 18,474.01 | 11.55 | 248,339.44 |
| Requested 255K (256K total) | 1K | 1 | 1 | 31.93 | 8,142.75 | 10.88 | 20,931.86 |

Observed behavior:

- At requested 64K ISL, E2E output throughput increases only from 265.17 to 288.66 tok/s while Input throughput plateaus at 16.97–18.47K tok/s. Mean TPOT remains nearly flat at 11.55–11.94 ms, but Mean TTFT rises from 37.57 to 248.34 seconds. The E2E result is therefore Prefill-limited; the 265–289 tok/s values must not be read as pure Decode capacity.
- The final row sends 261,120 input tokens and generates 1,024 output tokens, for 262,144 total sequence tokens. It is a requested-255K capability point, not a 256K-input claim.
- The customer report contains a matching 64K TPOT reference, but no matching 255K reference.

Machine-readable results: [`data/decode-long-context-results.tsv`](data/decode-long-context-results.tsv). Runtime identity, method, and source-artifact hashes: [`data/validation/decode-long-context-evidence.json`](data/validation/decode-long-context-evidence.json).

### 1P1D Prefill Scalability

| Input | Concurrency | Input tok/s | Mean TTFT (ms) |
|---:|---:|---:|---:|
| 8K | 1 | 16,835.22 | 485.70 |
| 8K | 2 | 19,618.25 | 829.40 |
| 8K | 4 | 18,161.81 | 1,612.03 |
| 8K | 8 | 21,004.97 | 2,817.91 |
| 64K | 1 | 18,057.01 | 3,628.49 |
| 64K | 2 | 19,860.45 | 6,481.41 |
| 64K | 4 | 18,763.17 | 12,970.83 |
| 64K | 8 | 18,765.43 | 22,530.68 |
| Nominal 256K | 1 | 12,381.87 | 21,170.66 |
| Nominal 256K | 2 | 12,378.06 | 41,208.61 |
| Nominal 256K | 4 | 12,389.64 | 77,254.06 |
| Nominal 256K | 8 | 12,402.23 | 133,251.83 |

Observed behavior:

- 8K Prefill reached 21,004.97 input tok/s at concurrency 8 in the complete matrix.
- 64K Prefill peaked at concurrency 2 and then stayed around 18.76K tok/s as concurrency increased.
- The nominal 256K rows used random-text prompt construction (`tokenize_prompt=false`). They describe scaling behavior only. The headline exact-token result is the separate targeted concurrency-4 run: **12,864.96 input tok/s**.

### Two-Node DP=2 Prefill Scalability

| Input | Concurrency | Aggregate input tok/s | Mean TTFT (ms) |
|---:|---:|---:|---:|
| 8K | 1 | 20,751.73 | 393.90 |
| 8K | 2 | 41,201.86 | 394.17 |
| 8K | 4 | 43,401.70 | 723.96 |
| 8K | 8 | 46,113.92 | 1,296.43 |
| 8K | 16 | 46,747.01 | 2,276.28 |
| 64K | 1 | 19,695.02 | 3,326.53 |
| 64K | 2 | 38,984.45 | 3,348.49 |
| 64K | 4 | 38,382.03 | 6,615.25 |
| 64K | 8 | 38,204.80 | 12,418.82 |
| 64K | 16 | 38,155.28 | 21,164.99 |
| Nominal 256K | 1 | 12,783.28 | 20,505.88 |
| Nominal 256K | 2 | 25,063.73 | 20,823.01 |
| Nominal 256K | 4 | 24,923.63 | 40,785.01 |
| Nominal 256K | 8 | 24,765.29 | 76,468.09 |

Observed behavior:

- DP=2 nearly doubled 8K and 64K aggregate Prefill throughput from concurrency 1 to 2, then reached a plateau.
- The DP=2 measurements used both workers behind the two-node router.
- No exact-token DP=2 256K rerun was completed. Those rows remain visible as nominal-length scalability observations and are excluded from the headline comparison.
- DP=2 is Prefill-only capacity; it is not 2P1D end-to-end throughput and does not measure P→D KV-cache transfer.

### 256K Methodology

| Evidence set | Client framing | Delivery use |
|---|---|---|
| Complete expanded matrix | Random-text construction, `tokenize_prompt=false` | Scaling and boundary observations; nominal 256K rows are not exact-token headline evidence |
| Targeted 1P1D 256K rerun | Exactly 262,144 token IDs, `--tokenize-prompt` | Headline result: 12,864.96 input tok/s |
| Current `scripts/amd-latest/` | Exact token IDs for every 256K-input Prefill benchmark | Required reproduction path for future 256K-input Prefill results |
| Final baked-image long-context Decode | Random-text framing; requested 64K input and requested 255K input + 1K output | MI300X capability/scalability only; not a 256K-input or H200-parity claim |

### Machine-Readable Evidence

- Headline point set: [`data/final-results.tsv`](data/final-results.tsv)
- Detailed scalability results: [`data/scalability-results.tsv`](data/scalability-results.tsv)
- Core Decode repeatability: [`data/decode-repeatability.tsv`](data/decode-repeatability.tsv)
- Long-context Decode results: [`data/decode-long-context-results.tsv`](data/decode-long-context-results.tsv)
- Long-context runtime and source-artifact evidence: [`data/validation/decode-long-context-evidence.json`](data/validation/decode-long-context-evidence.json)
- Exact-token and runtime validation metadata: [`data/validation/`](data/validation/)
- Supported reproduction bundle: [`scripts/amd-latest/`](scripts/amd-latest/)
- Repository quality gate: `python3 scripts/validate_repo.py` (expected final line: `REPO_VALIDATION=PASS`)

---

## Hardware & Software Stack

### Compute — Two-Node Azure MI300X Cluster

| Property | Value |
|----------|-------|
| Azure SKU | `Standard_ND96isr_MI300X_v5` (8× MI300X per node) |
| GPU | AMD Instinct MI300X, `gfx942` (CDNA 3), **192 GB HBM3**, 5.3 TB/s max peak theoretical |
| Nodes | 2 (VMSS, same placement group — IB guaranteed) |
| Total GPU Memory | **16× 192 GB = 3,072 GB** |
| InfiniBand | 8× CX7 400G NDR per node, measured **368 Gbps** per port |

### Software Stack

| Component | Version | Notes |
|-----------|---------|-------|
| Validated runtime image | `mimomi300xacr.azurecr.io/mimo-v2.5-pro-mi300x@sha256:08deabd2f3a4e98e183944048730f560056b0e4dd724c06f74c368645a655910` | Private ACR; 37 layers; clean Docker pull verified |
| Base image provenance | `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` | Base image ID `sha256:bb9d2e5ab1a6...` |
| SGLang | Package `0.0.0.dev14147+g2f9b9aedf.d20260706`, source HEAD `2f9b9aedf` | Final tested runtime |
| AITER | Source HEAD `00e94abf`; tuned CSV SHA-256 `2c87ff1...80ea7` | Final tested runtime |
| ROCm | 7.2.0 | |
| GEMM path | **CK A8W8 blockwise bpreshuffle** | `SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1` |
| Mooncake | `0.3.7.post2` | KV cache transfer for PD disaggregation |
| PyTorch | 2.9.1+rocm7.2.0 | ROCm backend |

### Model

| Property | Value | Source |
|----------|-------|--------|
| Model | [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) | HuggingFace |
| Total parameters | 1.02 T | HF Model Card |
| Active parameters | 42 B per token | HF Model Card |
| Routed experts | 384, 8 active per token | HF Model Card |
| Attention | Hybrid: 10 Global + 60 SWA (window=128) | HF Model Card |
| MTP | 3-layer multi-layer EAGLE | HF Model Card |
| Quantization | FP8 E4M3 | HF Model Card |
| Checkpoint size | 963 GB (34 safetensors) | Measured |

---

## Running on Azure and Reproducing Final Results

Use the immutable baked runtime below. It contains the tested SGLang/AITER source trees, Python/runtime deltas, tuned fused-MoE configuration, RDMA userspace stack, and [`scripts/amd-latest/`](scripts/amd-latest/) at `/opt/mimo-mi300x/scripts/amd-latest`.

### Prerequisites

- 2× Azure `Standard_ND96isr_MI300X_v5` nodes (VMSS, same placement group for IB)
- Repository-scoped ACR pull username and password, supplied through a private channel
- Model: [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) downloaded to `/data/models/MiMo-V2.5-Pro`
- Benchmark dataset available under `/data`; model weights and datasets are not included in the image
- The PD-separated Decode container must expose RDMA devices, `/dev/mem`, and `CAP_SYS_ADMIN`

### Pull and Start the Runtime — Both Nodes

The container requires elevated host access for RDMA memory registration. Run it only on dedicated, trusted benchmark nodes.

```bash
export ACR_LOGIN_SERVER=mimomi300xacr.azurecr.io
export IMAGE_REF='mimomi300xacr.azurecr.io/mimo-v2.5-pro-mi300x@sha256:08deabd2f3a4e98e183944048730f560056b0e4dd724c06f74c368645a655910'

read -rp 'ACR pull username: ' ACR_USERNAME
read -rsp 'ACR pull password: ' ACR_PASSWORD && printf '\n'
printf '%s' "$ACR_PASSWORD" | docker login "$ACR_LOGIN_SERVER" \
	--username "$ACR_USERNAME" --password-stdin
docker pull "$IMAGE_REF"
docker logout "$ACR_LOGIN_SERVER"
unset ACR_USERNAME ACR_PASSWORD

docker run -d --name mimo-mi300x \
	--privileged --network=host --ipc=host --shm-size=256g \
	--device=/dev/kfd --device=/dev/dri --device=/dev/mem \
	--cap-add=CAP_SYS_ADMIN --cap-add=SYS_PTRACE \
	--security-opt seccomp=unconfined --security-opt label=disable \
	--group-add video -v /data:/data \
	--entrypoint /bin/bash "$IMAGE_REF" -lc 'sleep infinity'

docker exec mimo-mi300x bash -lc '
	set -euo pipefail
	test "$(git -C /sgl-workspace/sglang_0625 rev-parse HEAD)" = 2f9b9aedf32977bc5d088a86ec0a73bcf432a4d0
	test "$(git -C /sgl-workspace/aiter_0625 rev-parse HEAD)" = 00e94abf15e1e09ab7cf481e989bca5d19a99b82
	test "$(sha256sum /sgl-workspace/aiter_0625/aiter/configs/model_configs/mimo_v2_5_pro_b16_tuned_fmoe.csv | cut -d" " -f1)" = 2c87ff1fa062c73e1941962f8630a335ea1e39d2dbb5b0c2d4971bcd55880ea7
	test -e /dev/infiniband/uverbs0
	test -e /dev/mem
	cd /opt/mimo-mi300x/scripts/amd-latest
	sha256sum -c SHA256SUMS.txt
'
```

The exact image identity and clean-pull evidence are in [`data/validation/container-image.json`](data/validation/container-image.json).

### 1P1D

```bash
# Enter the container on each node, then use the embedded bundle.
docker exec -it mimo-mi300x bash
cd /opt/mimo-mi300x/scripts/amd-latest
export MODEL=/data/models/MiMo-V2.5-Pro
export DATASET_PATH=/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json
read -rp 'Prefill node IB IP: ' PREFILL_IB_IP
read -rp 'Decode node IB IP: ' DECODE_IB_IP
export PREFILL_IB_IP DECODE_IB_IP

# Start workers in separate terminals on their respective nodes:
bash launch_pd_prefill.sh
bash launch_pd_decode.sh

# Prefill node capacity gate:
python3 validate_server_info.py http://127.0.0.1:30000/server_info \
	--output /data/mimo-amd-latest/onep/evidence/prefill-server-info.json

# Decode node capacity gate:
python3 validate_server_info.py http://127.0.0.1:30001/server_info \
	--output /data/mimo-amd-latest/onep/evidence/decode-server-info.json

# After both capacity gates pass, start the router on the Prefill node:
bash launch_pd_router.sh

# Router readiness gate:
curl -fsS --max-time 30 http://127.0.0.1:40000/v1/models >/dev/null

# Run on the router node after all three gates pass:
bash benchmark_1p_prefill.sh
bash benchmark_decode.sh
```

The immutable image contains the original headline bundle. The long-context Decode script was added to this repository after that image was published; it is executed against the same immutable runtime without changing the image. Clone or copy the current repository under `/data`, then run:

```bash
cd /data/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/amd-latest
export MODEL=/data/models/MiMo-V2.5-Pro
export DATASET_PATH=/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json
export PYTHONPATH="/sgl-workspace/sglang_0625/python${PYTHONPATH:+:$PYTHONPATH}"
bash benchmark_decode_long_context.sh
```

After the run, copy the Decode node evidence to the router node so the three service logs and two `server-info.json` files are colocated, preserving the basenames below. Then run:

```bash
cd /opt/mimo-mi300x/scripts/amd-latest
EVIDENCE=/data/mimo-amd-latest/onep/evidence

python3 validate_service_logs.py \
	"$EVIDENCE/prefill_outer.log" \
	"$EVIDENCE/decode_outer.log" \
	"$EVIDENCE/router_outer.log" \
	--profile onep \
	--output "$EVIDENCE/service-validation.json"

python3 validate_exact_256k.py \
	/data/mimo-amd-latest/onep/prefill/benchmark_262144_out1_con4.log \
	--prefill-info "$EVIDENCE/prefill-server-info.json" \
	--decode-info "$EVIDENCE/decode-server-info.json" \
	--service-logs \
		"$EVIDENCE/prefill_outer.log" \
		"$EVIDENCE/decode_outer.log" \
		"$EVIDENCE/router_outer.log" \
	--output "$EVIDENCE/exact-token-256k.json"
```

### DP=2 Two-Node Prefill

```bash
cd /opt/mimo-mi300x/scripts/amd-latest
bash launch_dp2_node0.sh
bash launch_dp2_node1.sh

# Validate node0 and node1 directly before starting the router:
python3 validate_server_info.py http://127.0.0.1:30000/server_info \
	--output /data/mimo-amd-latest/dp2/evidence/node0-server-info.json
python3 validate_server_info.py http://127.0.0.1:30001/server_info \
	--output /data/mimo-amd-latest/dp2/evidence/node1-server-info.json

read -rp 'Node0 IB IP: ' Node0_IP
read -rp 'Node1 IB IP: ' Node1_IP
export Node0_IP Node1_IP
bash launch_dp2_router.sh
curl -fsS --max-time 30 http://127.0.0.1:40000/v1/models >/dev/null
bash benchmark_dp2_prefill.sh
```

The convenience script above runs all three points. For reportable per-point distribution evidence, start fresh DP=2 services, capture `grep -c 'POST /generate'` from each worker log immediately before and after one `run_point`, then validate the four recorded integers. Repeat this sequence for 8K, 64K, and 256K:

```bash
cd /opt/mimo-mi300x/scripts/amd-latest
export LOG_DIR=/data/mimo-amd-latest/dp2
source ./benchmark_common.sh

# Run one point at a time on node0 after recording both before-counts:
run_point 8192 1 16 32 1 900 'Input token throughput'
# run_point 65536 1 2 32 1 900 'Input token throughput'
# run_point 262144 1 2 32 1 1200 'Input token throughput' token_ids

# On node0 and node1, respectively, record before/after counts from:
grep -c 'POST /generate' /data/mimo-amd-latest/dp2/service/node0_outer.log || true
grep -c 'POST /generate' /data/mimo-amd-latest/dp2/service/node1_outer.log || true

read -rp 'Node0 before count: ' NODE0_BEFORE
read -rp 'Node0 after count: ' NODE0_AFTER
read -rp 'Node1 before count: ' NODE1_BEFORE
read -rp 'Node1 after count: ' NODE1_AFTER
python3 write_distribution.py \
	--node0-before "$NODE0_BEFORE" --node0-after "$NODE0_AFTER" \
	--node1-before "$NODE1_BEFORE" --node1-after "$NODE1_AFTER" \
	--expected-total 33 \
	--output /data/mimo-amd-latest/dp2/benchmark_8192_out1_con16.distribution.tsv
```

After colocating the three DP=2 service logs, run:

```bash
cd /opt/mimo-mi300x/scripts/amd-latest
EVIDENCE=/data/mimo-amd-latest/dp2/evidence
python3 validate_service_logs.py \
	"$EVIDENCE/node0_outer.log" \
	"$EVIDENCE/node1_outer.log" \
	"$EVIDENCE/router_outer.log" \
	--profile dp2 \
	--output "$EVIDENCE/service-validation.json"
```

A DP=2 point is reportable only when the client gate passes, both worker deltas are positive and sum to 33 requests (32 measured + 1 warmup), and the service-log gate passes.

### Cleanup

```bash
docker rm -f mimo-mi300x
```

---

## Required Runtime Settings

| Setting | Requirement |
|---|---|
| Decode CUDA Graph | Keep enabled. Prefill disables CUDA Graph. |
| 256K request framing | Use context length 262151 and `--tokenize-prompt`; require `max_req_input_len>=262145`. |
| Router health | Use the non-generative `/server_info` endpoint with a 30-second timeout. |

---

## References

- [Azure ND-MI300X-v5 size series](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/ndmi300xv5-series)
- [AMD Instinct MI300X datasheet](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/data-sheets/amd-instinct-mi300x-data-sheet.pdf)
- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` branch](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [MiMo model-specific fused-MoE tuning — `aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)
