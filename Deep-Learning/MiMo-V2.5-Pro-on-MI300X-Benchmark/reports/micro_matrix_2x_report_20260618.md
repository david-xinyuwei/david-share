# EP8 Micro Matrix Two-Round Result — 2026-06-18

This report records the completed two-round EP8/DP1 PD-router benchmark for Xiaomi MiMo-V2.5-Pro on a two-node Azure MI300X setup.

Raw summary TSV: [`../data/micro_matrix_2x_summary_20260618.tsv`](../data/micro_matrix_2x_summary_20260618.tsv)

## Run Configuration

| Item | Value |
|---|---|
| Topology | 1P+1D PD router, `TP=8`, local `EP=8`, `DP=1` |
| Transfer backend | Mooncake |
| MoE backend | MORI |
| Speculative decode | EAGLE / MTP layer=3 |
| Router endpoint | `http://127.0.0.1:40000` |
| Dataset | random fixed-length prompts, seed `12345` |
| Repeats | 2 |
| Stale handling | watchdog killed stale benchmark clients only; router/prefill/decode services were not restarted by watchdog |

## Two-Round Averages

### Prefill

| Context | Avg MI300X input tok/s | H200 EP16/DP2 tok/s | MI300X/H200 | Status |
|---:|---:|---:|---:|:---:|
| 8K | 13,530.83 | 31,950 | 42.4% | OK |
| 64K | 11,500.10 | 27,400 | 42.0% | OK |
| 256K | — | 17,400 | — | Stuck under repeated/concurrent PD-router traffic |

### Decode 8K

| BS | Avg output tok/s | Avg TPOT ms | H200 TPOT ms | MI300X/H200 TPOT | Status |
|---:|---:|---:|---:|---:|:---:|
| 16 | 682.36 | 13.71 | 11.59 | 1.18x slower | OK |
| 32 | 961.58 | 16.53 | 12.56 | 1.32x slower | OK |
| 64 | 1,244.16 | 19.70 | 14.28 | 1.38x slower | OK |
| 128 | 1,513.52 | 22.16 | 18.25 | 1.21x slower | OK |
| 192 | 1,609.61 | 22.56 | 23.29 | 0.97x, parity/slightly faster | OK |
| 256 | 1,694.96 | 22.86 | 27.38 | 0.83x, faster | OK |

### Decode 64K

| BS | Avg output tok/s | Avg TPOT ms | H200 TPOT ms | MI300X/H200 TPOT | Status |
|---:|---:|---:|---:|---:|:---:|
| 16 | 143.06 | 23.36 | 11.99 | 1.95x slower | OK |
| 32 | 157.64 | 23.37 | 14.31 | 1.63x slower | OK |
| 64 | 171.81 | 24.39 | 16.33 | 1.49x slower | OK |
| 96 | 176.82 | 24.18 | 19.63 | 1.23x slower | OK |

### 256K Decode

| Case | Status |
|---|---|
| `decode_ctx256k_bs16`, both repeats | `STUCK_WATCHDOG_KILLED` |
| `decode_ctx256k_bs32`, both repeats | `STUCK_WATCHDOG_KILLED` |

## Interpretation

1. The strongest current result is 8K decode at high batch: MI300X reaches H200 parity at BS192 and is faster at BS256 on TPOT.
2. 64K decode remains slower than the H200 EP32/DP4 reference, although the gap narrows at higher batch sizes.
3. Prefill remains the largest throughput gap: current EP8/DP1 MI300X is about 42% of the H200 EP16/DP2 reference for 8K and 64K.
4. 256K repeated/concurrent traffic remains unstable under the PD router path. The result rows marked `STUCK_*` are not valid performance numbers.

## Evidence

The tracked raw summary TSV was pulled from VM8 container path `/data/bench_ep8_micro_2x/summary.tsv` after the matrix reached `ALL DONE`. Full per-case logs were also pulled to the working workspace for audit, but this public repo tracks the compact TSV summary rather than compressed log archives.
