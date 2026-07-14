# AMD Tuned Fused-MoE Expanded Concurrency Reproduction (2026-07-13)

Run ID: `tuned_moe_robustness_20260713T064358Z`

This is one complete 35-point expanded matrix, not a full-matrix N=3 claim.
Every accepted point passed exact request-count, context, client, service-log,
and topology-specific gates. DP=2 is a two-worker prefill-only capacity test;
it is not a 2P1D end-to-end throughput measurement.

## AMD Original-Script Verification and 256K Boundary

The AMD launch, router, and prefill benchmark scripts named in `测试方法.txt` were copied read-only from the source container workspace and verified against source-node SHA-256 values. The benchmark script was run with exactly one change: its token list was narrowed from `8K/64K/256K` to `8K/64K` so that the known-invalid 256K row would not execute. The copied original client uses random input, output 1, concurrency 4, 16 prompts, one warmup, `--flush-cache`, seed 12345, and `--pd-separated`.

| Input / output | AMD screenshot tuned tok/s | Exact-script tok/s | Delta | Requests |
|---|---:|---:|---:|---:|
| 8K / 1 | 20,689.70 | 20,305.98 | -1.85% | 16 / 16 |
| 64K / 1 | 18,689.51 | 18,694.26 | +0.03% | 16 / 16 |

The latest valid Microsoft 1P1D 256K/concurrency-4 confirmation is `12,393.19 tok/s`, with 16/16 retokenized outputs and zero context/fatal markers. The supplied AMD launch script uses `--context-length 262144`; our same-script reproduction produced `39,905.41 tok/s` but only 5/16 retokenized outputs and eleven matching `262148 > 262144` service errors. HTTP 200 error payloads were counted as full successful inputs. AMD did not provide the raw client/service logs for its `39,279.65 tok/s` screenshot row, so its exact failure count is unknown. The corrected run changes both server allowances to 262151 and passes direct capacity gates. Do not calculate a valid 256K uplift or deficit from the screenshot value.

## Valid Improvement over the July 7 CK Path

| Surface | Workload | July 7 CK tok/s | July 13 tuned tok/s | Change |
|---|---|---:|---:|---:|
| Decode | 8K/1K, c16 | 1,299.18 | 1,303.44 | +0.33% |
| Decode | 8K/1K, c32 | 1,910.75 | 1,930.10 | +1.01% |
| Decode | 8K/1K, c64 | 2,188.05 | 2,462.83 | +12.56% |
| Decode | 8K/1K, c128 | 2,209.43 | 2,468.95 | +11.75% |
| 1P1D Prefill | 8K/1, c4 | 16,715.80 | 20,305.98 | +21.48% |
| 1P1D Prefill | 64K/1, c4 | 17,254.14 | 18,694.26 | +8.35% |

These are independent valid fresh-service measurements rather than a same-process paired A/B. They confirm a material tuned-MoE gain at 8K/64K Prefill and Decode c64/c128, with smaller positive changes at Decode c16/c32. The invalid 256K July 7 and supplier screenshot values are excluded from this uplift table.

One complete expanded matrix was requested and executed. This report does not claim full-matrix N=3 or CV.

## Decode 8K/1K

| Concurrency | Success | Output tok/s | Mean TPOT ms | Mean TTFT ms | Status |
|---|---|---|---|---|---|
| 8 | 256 | 930.00 | 7.65 | 863.69 | ACCEPTED |
| 16 | 256 | 1303.44 | 10.72 | 1398.73 | ACCEPTED |
| 32 | 256 | 1930.10 | 13.68 | 2296.89 | ACCEPTED |
| 64 | 256 | 2462.83 | 17.08 | 7406.18 | ACCEPTED |
| 96 | 256 | 2497.69 | 15.89 | 18273.38 | ACCEPTED |
| 128 | 256 | 2468.95 | 16.45 | 27128.38 | ACCEPTED |
| 192 | 256 | 2500.54 | 15.98 | 40956.57 | ACCEPTED |
| 256 | 256 | 729.98 | 108.58 | 29013.34 | REJECTED |

## Core Decode Fresh-Service Repeatability

| Concurrency | Fresh run 1 tok/s | Fresh run 2 tok/s | Throughput delta | Mean TPOT delta |
|---|---|---|---|---|
| 16 | 1331.98 | 1303.44 | -2.14% | -1.02% |
| 32 | 1936.24 | 1930.10 | -0.32% | +0.22% |
| 64 | 2457.73 | 2462.83 | +0.21% | +0.47% |
| 128 | 2486.89 | 2468.95 | -0.72% | -0.66% |

## 1P1D Prefill

| Input | Concurrency | Success | Input tok/s | Worker request deltas | Status |
|---|---|---|---|---|---|
| 8192 | 1 | 16 | 16835.22 |  | ACCEPTED |
| 8192 | 2 | 16 | 19618.25 |  | ACCEPTED |
| 8192 | 4 | 16 | 18161.81 |  | ACCEPTED |
| 8192 | 8 | 16 | 21004.97 |  | ACCEPTED |
| 65536 | 1 | 16 | 18057.01 |  | ACCEPTED |
| 65536 | 2 | 16 | 19860.45 |  | ACCEPTED |
| 65536 | 4 | 16 | 18763.17 |  | ACCEPTED |
| 65536 | 8 | 16 | 18765.43 |  | ACCEPTED |
| 262144 | 1 | 16 | 12381.87 |  | ACCEPTED |
| 262144 | 2 | 16 | 12378.06 |  | ACCEPTED |
| 262144 | 4 | 16 | 12389.64 |  | ACCEPTED |
| 262144 | 8 | 16 | 12402.23 |  | ACCEPTED |

The 256K/c4 point was independently rerun after changing only the Prefill and Decode server allowance from 262144 to 262151. It completed 16/16 requests and 16/16 retokenized outputs at `12,393.19 tok/s`, only +0.03% above the full-matrix value.

## DP=2 Prefill

| Input | Concurrency | Success | Input tok/s | Worker request deltas | Status |
|---|---|---|---|---|---|
| 8192 | 1 | 32 | 20751.73 | 17/16 | ACCEPTED |
| 8192 | 2 | 32 | 41201.86 | 16/17 | ACCEPTED |
| 8192 | 4 | 32 | 43401.70 | 17/16 | ACCEPTED |
| 8192 | 8 | 32 | 46113.92 | 16/17 | ACCEPTED |
| 8192 | 16 | 32 | 46747.01 | 17/16 | ACCEPTED |
| 65536 | 1 | 32 | 19695.02 | 16/17 | ACCEPTED |
| 65536 | 2 | 32 | 38984.45 | 17/16 | ACCEPTED |
| 65536 | 4 | 32 | 38382.03 | 16/17 | ACCEPTED |
| 65536 | 8 | 32 | 38204.80 | 17/16 | ACCEPTED |
| 65536 | 16 | 32 | 38155.28 | 16/17 | ACCEPTED |
| 262144 | 1 | 32 | 12783.28 | 17/16 | ACCEPTED |
| 262144 | 2 | 32 | 25063.73 | 17/16 | ACCEPTED |
| 262144 | 4 | 32 | 24923.63 | 16/17 | ACCEPTED |
| 262144 | 8 | 32 | 24765.29 | 17/16 | ACCEPTED |
| 262144 | 16 | 24 | 18742.17 |  | REJECTED |

## Acceptance Summary

- Matrix points: 35
- Accepted points: 33
- Rejected points: 2
- DP=2 is prefill-only capacity and is not 2P1D end-to-end throughput.

## Observed Failed Attempts

- `dp2-256k-c2-gpu-fault`: 2 archived service logs contain hard-fail markers. A successful fresh-service retry does not erase this robustness incident.

- Rejected boundary decode:8192:1024:256: prefill watchdog dump
- Rejected boundary dp2:262144:1:16: unexpected successful-request count; client fatal marker; invalid two-worker distribution; GPU memory-aperture fault

## Public Evidence

See `../data/raw-logs/20260713-amd-tuned-moe-expanded-concurrency/` for sanitized point evidence,
structured service and capacity validation, and SHA-256 manifests.
