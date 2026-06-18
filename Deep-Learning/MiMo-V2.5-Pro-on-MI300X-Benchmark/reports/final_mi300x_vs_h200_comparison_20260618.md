# Final MI300X vs H200 Comparison — 2026-06-18

This report separates prefill throughput, decode TPOT, decode per-stream tokens/s, and MI300X long-context boundary results. The goal is to avoid mixing different metrics or topologies.

## Methodology Notes

- Prefill is compared by input token throughput.
- Decode TPOT is compared directly where H200 reference TPOT exists.
- Decode per-stream tokens/s is calculated as `1000 / TPOT(ms)` for both MI300X and H200.
- MI300X long-context BS=1 boundary results do not have an H200 BS=1 counterpart in the provided reference, so they are reported as MI300X capability results rather than a direct H200 parity claim.
- MI300X topology for the completed baseline is `TP=8, local EP=8, DP=1`, 1P+1D PD router. H200 reference uses stronger global EP/DP settings, so this is an aligned workload comparison, not an identical-topology comparison.

## Executive Summary

| Area | Current Result | H200 Parity Status |
|---|---|---|
| Prefill | MI300X is about 42% of H200 EP16/DP2 | Not close yet |
| Decode 8K high batch | MI300X matches or exceeds H200 per-stream tokens/s at BS192/BS256 | Parity/above at high batch |
| Decode 64K | MI300X reaches 51-81% of H200 per-stream tokens/s | Not yet parity |
| Long-context decode boundary | MI300X reaches 255.25K context with output=1024, BS=1 | Capability is near 256K, but no H200 BS=1 reference |
| 255.375K output threshold | output=1/64/256/512/768 OK; output=1024 stale | Localizes stale to long generation / response-drain |

## Prefill Throughput

| Context | MI300X input tok/s | H200 input tok/s | MI300X / H200 | Status |
|---:|---:|---:|---:|---|
| 8K | 13,531 | 31,950 | 42.4% | Not parity |
| 64K | 11,500 | 27,400 | 42.0% | Not parity |
| 256K isolated | 7,239-7,294 | 17,400 | 41.6-41.9% | Single request works; repeated/concurrent path unstable |

## Decode TPOT Comparison

TPOT is time per output token. Lower is better.

| Context | Batch | MI300X TPOT | H200 TPOT | MI300X / H200 | Status |
|---:|---:|---:|---:|---:|---|
| 8K | 16 | 13.71 ms | 11.59 ms | 1.18x slower | Not parity |
| 8K | 32 | 16.53 ms | 12.56 ms | 1.32x slower | Not parity |
| 8K | 64 | 19.70 ms | 14.28 ms | 1.38x slower | Not parity |
| 8K | 128 | 22.16 ms | 18.25 ms | 1.21x slower | Nearer, still slower |
| 8K | 192 | 22.56 ms | 23.29 ms | 0.97x | Slightly faster than H200 |
| 8K | 256 | 22.86 ms | 27.38 ms | 0.83x | Faster than H200 |
| 64K | 16 | 23.36 ms | 11.99 ms | 1.95x slower | Not parity |
| 64K | 32 | 23.37 ms | 14.31 ms | 1.63x slower | Not parity |
| 64K | 64 | 24.39 ms | 16.33 ms | 1.49x slower | Not parity |
| 64K | 96 | 24.18 ms | 19.63 ms | 1.23x slower | Closest 64K point, still slower |

## Decode Per-Stream Tokens/s

Per-stream tokens/s is calculated as `1000 / TPOT(ms)`. Higher is better.

| Context | Batch | MI300X tok/s | H200 tok/s | MI300X / H200 | Status |
|---:|---:|---:|---:|---:|---|
| 8K | 16 | 72.9 | 86.3 | 84.5% | Not parity |
| 8K | 32 | 60.5 | 79.6 | 76.0% | Not parity |
| 8K | 64 | 50.8 | 70.0 | 72.5% | Not parity |
| 8K | 128 | 45.1 | 54.8 | 82.4% | Nearer, still slower |
| 8K | 192 | 44.3 | 42.9 | 103.2% | Slightly faster than H200 |
| 8K | 256 | 43.7 | 36.5 | 119.8% | Faster than H200 |
| 64K | 16 | 42.8 | 83.4 | 51.3% | Not parity |
| 64K | 32 | 42.8 | 69.9 | 61.2% | Not parity |
| 64K | 64 | 41.0 | 61.2 | 66.9% | Not parity |
| 64K | 96 | 41.4 | 50.9 | 81.2% | Closest 64K point, still slower |

## MI300X Long-Context Decode Capability

These are MI300X BS=1, output=1024, streaming results. There is no H200 BS=1 reference in the provided data, so this table is not a direct H200 comparison.

| Context | Input length | Status | TPOT | Per-stream tok/s | Bench output tok/s |
|---:|---:|---|---:|---:|---:|
| 192K | 196,608 | OK | 47.48 ms | 21.1 | 14.16 |
| 224K | 229,376 | OK | 53.55 ms | 18.7 | 12.15 |
| 240K | 245,760 | OK | 56.57 ms | 17.7 | 11.31 |
| 248K | 253,952 | OK | 58.15 ms | 17.2 | 11.04 |
| 252K | 258,048 | OK | 58.86 ms | 17.0 | 10.77 |
| 254K | 260,096 | OK | 59.29 ms | 16.9 | 10.66 |
| 255K | 261,120 | OK | 59.45 ms | 16.8 | 10.61 |
| 255.25K | 261,376 | OK | 59.49 ms | 16.8 | 10.64 |
| 255.375K | 261,504 | STALE_KILLED | — | — | — |

## 255.375K Output-Length Diagnostic

At 255.375K context, only output length is changed.

| Output length | Status | TPOT | Per-stream tok/s | Interpretation |
|---:|---|---:|---:|---|
| 1 | OK | 0.00 ms | — | Handoff / KV transfer completes |
| 64 | OK | 62.44 ms | 16.0 | Short decode generation completes |
| 256 | OK | 60.03 ms | 16.7 | Medium decode generation completes |
| 512 | OK | 59.87 ms | 16.7 | Long decode generation completes |
| 768 | OK | 59.66 ms | 16.8 | Long decode generation still completes |
| 1024 | STALE_KILLED | — | — | Repeatedly enters stale state |

## Final Interpretation

MI300X has made strong progress in context capability: the current EP8/DP1 PD-router setup can decode at 255.25K context with output=1024 and can complete up to 768 generated tokens at 255.375K context.

However, this does not mean full H200 parity. Prefill remains around 42% of H200, 64K decode remains below H200, and near-256K long-output decode still hits a request-level stale condition. The strongest parity result is 8K decode at high batch, where MI300X matches or exceeds H200 per-stream tokens/s.
