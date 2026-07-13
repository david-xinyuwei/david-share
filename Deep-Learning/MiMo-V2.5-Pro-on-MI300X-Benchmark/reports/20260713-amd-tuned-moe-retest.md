# AMD Tuned Fused-MoE Independent Retest (2026-07-13)

## Scope

This report records an independent two-node Azure MI300X retest of the MiMo-V2.5-Pro model-specific fused-MoE tuning configuration introduced by [`sammysun0711/aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9).

The public commit adds two model configuration CSV files; it does not change the fused-MoE kernel source. Accordingly, this report calls the change **model-specific fused-MoE tuning configuration**, not a new kernel implementation.

Run ID: `tuned_moe_retest_20260713T014113Z`

## Environment

| Component | Value |
|---|---|
| Azure nodes | 2 x `Standard_ND96isr_MI300X_v5` |
| GPUs | 8 x MI300X per node, TP=8 per server |
| Docker image | `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` |
| SGLang | AMD `mimo_aiter_attn` source, `/sgl-workspace/sglang_0625` |
| aiter | Public equivalent commit `d725746a0f8c233d8e46e2771a7c8dbcd06e40d9` |
| PyTorch | `2.9.1+rocm7.2.0.git7e1940d4` |
| Attention backend | AITER |
| GEMM path | CK A8W8 blockscale bpreshuffle |
| MTP | Multi-layer EAGLE, simulated accept length 3 |

The tuned CSV SHA-256 is `2c87ff1fa062c73e1941962f8630a335ea1e39d2dbb5b0c2d4971bcd55880ea7`. The runtime log confirmed that aiter merged `mimo_v2_5_pro_b16_tuned_fmoe.csv` into its active fused-MoE configuration.

## Acceptance Gates

| Matrix | Points | Requests per point | Exit code | Client error markers |
|---|---:|---:|---:|---:|
| Decode 8K/1K | 4 | 256 | 0 | 0 |
| 1P1D Prefill 8K/64K/256K | 3 | 16 | 0 | 0 |
| DP=2 Prefill 8K/64K/256K x concurrency 4/8 | 6 | 32 | 0 | 0 |

## Decode Results

Input length is 8,192 tokens; output length is 1,024 tokens; warmup is 32 requests. The prior strict baseline is our independently reproduced 2026-07-07 CK run.

| Concurrency | Successful requests | Output tok/s | Mean TPOT ms | Median TPOT ms | P99 TPOT ms | Output vs strict baseline | Mean TPOT vs strict baseline |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 256 | 1,331.98 | 10.83 | 10.97 | 11.35 | +2.52% | +1.79% |
| 32 | 256 | 1,936.24 | 13.65 | 13.93 | 14.35 | +1.33% | +1.11% |
| 64 | 256 | 2,457.73 | 17.00 | 17.60 | 18.44 | +12.33% | +12.58% |
| 128 | 256 | 2,486.89 | 16.56 | 17.30 | 17.92 | +12.56% | +14.05% |

At concurrency 64 and 128, the tuned configuration raises output throughput by about 12%, while mean TPOT also rises by 13-14%. This is a throughput/latency trade-off, not an across-the-board latency improvement.

Against the Xiaomi H200 reference, MI300X median TPOT is 0.95x, 1.11x, 1.23x, and 0.95x at concurrency 16, 32, 64, and 128 respectively. Output throughput is not topology-normalized and is reported separately.

## 1P1D Prefill Results

Output length is 1 token; concurrency is 4; each point has 16 successful requests.

| Input tokens | Input tok/s | vs 2026-07-07 strict baseline | MI300X / H200 reference |
|---:|---:|---:|---:|
| 8,192 | 20,780.79 | +24.32% | 65.0% |
| 65,536 | 19,022.57 | +10.25% | 69.4% |
| 262,144 | Excluded | Excluded | Excluded |

The 8K and 64K points are valid. The 256K client summary is excluded: node 0 and node 1 each logged 11 context-overflow responses because the 262,144-token server allowance was smaller than the 262,148-token server-side request. A corrected 262,149-token rerun is required before publishing 1P1D 256K throughput.

## DP=2 Prefill Results

This is a prefill-only server-mode test with two TP=8 servers behind the DP router. It does not include P-to-D KV-cache transfer and is not a 2P1D end-to-end measurement.

| Input tokens | Concurrency | Successful requests | Aggregate tok/s | Per-node tok/s | Per-node / H200 reference |
|---:|---:|---:|---:|---:|---:|
| 8,192 | 4 | 32 | 43,221.12 | 21,610.56 | 67.6% |
| 8,192 | 8 | 32 | 45,992.94 | 22,996.47 | 72.0% |
| 65,536 | 4 | 32 | 38,374.65 | 19,187.33 | 70.0% |
| 65,536 | 8 | 32 | 38,255.28 | 19,127.64 | 69.8% |
| 262,144 | 4 | 32 | 74,611.25 | 37,305.62 | 214.4% |
| 262,144 | 8 | 32 | 78,613.96 | 39,306.98 | 225.9% |

The H200 comparison is per-node on the MI300X side. Aggregate DP=2 throughput must not be compared directly with a single H200 node.

## 256K Correctness Guard

The same client-only false-success pattern affected the original 1P1D 256K point: each server log contains 11 context-overflow responses. Its reported 39,905.41 tok/s is excluded.

The supplied DP=2 server setting `--context-length 262144` was insufficient for a `random_input_len=262144` request on the standard server path. The server observed 262,148 tokens and returned an error payload with HTTP 200. A client-only success counter therefore produced a false positive.

The invalid attempt is excluded. It produced 24 context-overflow entries on node 0 and 22 on node 1. The accepted rerun kept the requested input length at 262,144 and output length at 1, while increasing only the server allowance to 262,149. The final node logs contain zero context-overflow entries, and both 256K points completed 32/32 requests.

This guard is part of the published reproduction scripts in `launch_dp2_node0.sh` and `launch_dp2_node1.sh`.

## Evidence Map

| Evidence | Path |
|---|---|
| Deterministic result JSON | [`data/raw-logs/20260713-amd-tuned-moe-retest/results.json`](../data/raw-logs/20260713-amd-tuned-moe-retest/results.json) |
| Decode client logs | [`data/raw-logs/20260713-amd-tuned-moe-retest/decode/`](../data/raw-logs/20260713-amd-tuned-moe-retest/decode/) |
| 1P1D prefill client logs | [`data/raw-logs/20260713-amd-tuned-moe-retest/prefill/`](../data/raw-logs/20260713-amd-tuned-moe-retest/prefill/) |
| DP=2 prefill client logs | [`data/raw-logs/20260713-amd-tuned-moe-retest/dp2/`](../data/raw-logs/20260713-amd-tuned-moe-retest/dp2/) |
| Matrix and context checks | [`data/raw-logs/20260713-amd-tuned-moe-retest/checks/validation.txt`](../data/raw-logs/20260713-amd-tuned-moe-retest/checks/validation.txt) |
| Public evidence hashes | [`data/raw-logs/20260713-amd-tuned-moe-retest/SHA256SUMS.txt`](../data/raw-logs/20260713-amd-tuned-moe-retest/SHA256SUMS.txt) |
| Launch, benchmark, config, and parser bundle | [`scripts/20260713-amd-tuned-moe-retest/`](../scripts/20260713-amd-tuned-moe-retest/) |

## Boundaries

- AMD reported a 37.6% single-kernel latency reduction, but no standalone microbenchmark log was supplied in the shared evidence. That claim is not treated as an independently measured result here.
- The H200 source is Xiaomi-provided reference material. H200 prefill uses idealized balanced expert routing; MI300X uses real expert routing.
- Each matrix point is one benchmark run. The request count is reported, but no multi-run standard deviation is claimed.