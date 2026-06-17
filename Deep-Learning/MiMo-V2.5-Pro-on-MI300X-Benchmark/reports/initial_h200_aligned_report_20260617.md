# MiMo-V2.5-Pro on Azure MI300X vs H200 - Initial Aligned Result

Generated: 2026-06-17

Status: INITIAL_RESULT_WITH_RECOVERY_PASS_RUNNING

This report captures the first H200-aligned router-valid MI300X result. A two-round micro-matrix recovery pass is running separately to repeat the successful 8K/64K points and recover the 256K long-context points with bounded per-case timeouts.

## Configuration

- Hardware: 2 x Azure ND96isr_MI300X_v5, 8 x MI300X per node.
- Runtime: PD router endpoint `127.0.0.1:40000`, prefill `127.0.0.1:30000`, decode `127.0.0.1:30001`.
- Config: `TP=8`, `EP=8`, MORI, MTP/EAGLE layer=3, chunked prefill size=16384.
- Dataset: `--dataset-name random --random-range-ratio 1.0 --seed 12345`.
- Prefill server: context=786432, mem-fraction-static=0.75.
- Decode server: context=262144, mem-fraction-static=0.85.
- Valid output directory on VM8: `/data/bench_ep8_router_valid/`.

## Initial Executive Summary

- Prefill 8K and 64K completed cleanly: MI300X is about 42-53% of H200, depending which H200 prefill line is used.
- Decode 8K completed all H200 batch points. TPOT is 1.27-1.58x slower at BS16-64, roughly equal to faster at BS192-256.
- Decode 64K completed all H200 batch points. TPOT is 1.20-1.97x slower, with the gap narrowing at higher batch.
- 256K long-context points are not stable in the first monolithic run. They are being re-tested in a micro-matrix with per-case timeout and two repeats.

## Prefill Comparison

| Case | MI300X tok/s | Success | H200 EP16/DP2 | vs EP16 | H200 EP32/DP4 | vs EP32 | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| 8K | 14435.91 | 30/30 | 31950 | 45.2% | 27500 | 52.5% | Clean |
| 64K | 11445.42 | 30/30 | 27400 | 41.8% | 23000 | 49.8% | Clean |
| 256K | 217.38 | 6/20 | 17400 | 1.2% | 13425 | 1.6% | Not stable in monolithic run |
| 768K | not run | - | 8000 | - | 6788 | - | Separate long-context pass required |

## Decode TPOT Comparison

Lower TPOT is better.

| Context | BS | MI300X TPOT ms | H200 TPOT ms | MI300X vs H200 | Success | Output tok/s |
|---|---:|---:|---:|---:|---:|---:|
| 8K | 16 | 14.74 | 11.59 | 1.27x slower | 200/200 | 896.36 |
| 8K | 32 | 19.07 | 12.56 | 1.52x slower | 200/200 | 1345.41 |
| 8K | 64 | 22.57 | 14.28 | 1.58x slower | 200/200 | 1597.04 |
| 8K | 128 | 22.62 | 18.25 | 1.24x slower | 200/200 | 1609.42 |
| 8K | 192 | 22.79 | 23.29 | 0.98x H200 TPOT | 200/200 | 1656.07 |
| 8K | 256 | 22.78 | 27.38 | 0.83x H200 TPOT | 200/200 | 1628.16 |
| 64K | 16 | 23.65 | 11.99 | 1.97x slower | 200/200 | 179.60 |
| 64K | 32 | 23.61 | 14.31 | 1.65x slower | 200/200 | 179.34 |
| 64K | 64 | 23.77 | 16.33 | 1.46x slower | 200/200 | 179.81 |
| 64K | 96 | 23.60 | 19.63 | 1.20x slower | 200/200 | 178.98 |
| 256K | 16 | 59.40 | 13.93 | 4.26x slower | 10/100 | 0.95 |
| 256K | 32 | not completed | 16.94 | - | stopped | - |

## Recovery Plan Now Running

The current recovery script is `scripts/bench_micro_matrix_2x.sh`.

It runs:

- Prefill 8K, 64K, 256K low-concurrency points twice.
- Decode 8K all H200 batch points twice.
- Decode 64K all H200 batch points twice.
- Decode 256K BS16 and BS32 twice with per-case timeout.

Each case restarts the router, runs with fixed random input, and writes independent logs under `/data/bench_ep8_micro_2x/`.

## 256K Single-Request Diagnostic

After the micro-matrix showed the same 256K drain behavior, I ran an isolated 256K single-request diagnostic:

| Case | Input | Output | BS | Prompts | Result | Input tok/s | TTFT |
|---|---:|---:|---:|---:|---|---:|---:|
| prefill_256k_stream_on_n1 | 262144 | 1 | 1 | 1 | 1/1 success | 7315.27 | 35830.22 ms |

This proves 256K is not completely impossible on the current stack. The failure mode is triggered by repeated or concurrent 256K requests through the PD router path, where the router eventually reports incomplete response-body consumption.

I then ran the same 256K single-request diagnostic with streaming disabled:

| Case | Input | Output | BS | Prompts | Streaming | Result | Input tok/s | TTFT |
|---|---:|---:|---:|---:|---|---|---:|---:|
| prefill_256k_stream_on_n1 | 262144 | 1 | 1 | 1 | on | 1/1 success | 7315.27 | 35830.22 ms |
| prefill_256k_disable_stream_n1 | 262144 | 1 | 1 | 1 | off | 1/1 success | 7251.86 | 36143.90 ms |

This means streaming alone is not the root cause. The 256K failure boundary appears when repeated or concurrent long-context requests go through the PD router/prefill response-drain path.

Diagnostic TSV: [`data/diagnostic_256k_stream_vs_nostream_20260617.tsv`](data/diagnostic_256k_stream_vs_nostream_20260617.tsv)
Diagnostic report: [`reports/diagnostic_256k_stream_vs_nostream_20260617.md`](reports/diagnostic_256k_stream_vs_nostream_20260617.md)

## Evidence Files

- Initial summary TSV: `data/initial_router_valid_summary_20260617.tsv`
- Initial local report: `reports/initial_h200_aligned_report_20260617.md`
- Recovery script: `scripts/bench_micro_matrix_2x.sh`
- Original local report source: `G:\AI-Super-Agent\x小米H200\reports\mi300x-nightly-20260617\final_report.md`
