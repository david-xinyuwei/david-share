# Streaming Decode Context Boundary — 2026-06-18

This diagnostic narrows the long-context decode failure boundary for the EP8/DP1 PD-router stack using single-request streaming decode.

Raw summary TSV: [`../data/decode_context_boundary_20260618.tsv`](../data/decode_context_boundary_20260618.tsv)

## Run Configuration

| Item | Value |
|---|---|
| Topology | 1P+1D PD router, `TP=8`, local `EP=8`, `DP=1` |
| Transfer backend | Mooncake |
| MoE backend | MORI |
| Speculative decode | EAGLE / MTP layer=3 |
| Dataset | random fixed-length prompts, seed `12345` |
| Request shape | `num_prompts=1`, `max_concurrency=1`, `output_len=1024`, streaming enabled |
| Router handling | router restarted before each boundary case |
| Stale handling | a case is treated as stuck only after 300 seconds of no log progress plus idle GPU |

## Results

| Context | Status | Successful requests | Input tok/s | Output tok/s | TTFT ms | TPOT ms | Interpretation |
|---:|---|---:|---:|---:|---:|---:|---|
| 64K | OK | 1 | 2,191.78 | 34.25 | 6,340.27 | 23.03 | Baseline long-context decode succeeds. |
| 80K | OK | 1 | 2,361.72 | 29.52 | 8,011.51 | 26.07 | First refined boundary point succeeds. |
| 96K | OK | 1 | 2,467.85 | 25.71 | 10,023.18 | 29.14 | Refined boundary point succeeds. |
| 112K | OK | 1 | 2,554.92 | 22.81 | 11,938.27 | 32.20 | Refined boundary point succeeds. |
| 128K | OK | 1 | 2,615.72 | 20.44 | 14,027.17 | 35.27 | Previous manual-stuck observation was a premature stop; strict rerun succeeds. |
| 192K | OK | 1 | 2,717.80 | 14.16 | 23,761.84 | 47.48 | Long-context decode still succeeds. |
| 224K | OK | 1 | 2,722.55 | 12.15 | 29,462.12 | 53.55 | Near-256K decode still succeeds. |
| 240K | OK | 1 | 2,714.80 | 11.31 | 32,651.06 | 56.57 | Near-256K decode still succeeds. |
| 248K | OK | 1 | 2,738.14 | 11.04 | 33,249.16 | 58.15 | Near-256K decode still succeeds. |
| 252K | OK | 1 | 2,713.32 | 10.77 | 34,886.93 | 58.86 | Final high-context sweep succeeds. |
| 254K | OK | 1 | 2,707.26 | 10.66 | 35,410.47 | 59.29 | Final high-context sweep succeeds. |
| 255K | OK | 1 | 2,705.20 | 10.61 | 35,704.00 | 59.45 | Highest successful strict point so far. |
| 255.25K | OK | 1 | 2,716.38 | 10.64 | 35,363.74 | 59.49 | Highest successful strict point so far. |
| 255.375K | `STALE_KILLED` | — | — | — | — | — | Hit the 300s stale rule with idle GPU; not a performance number. |
| 255.5K | `STALE_KILLED` | — | — | — | — | — | Hit the 300s stale rule with idle GPU; not a performance number. |
| 256K | `STALE_KILLED` | — | — | — | — | — | Hit the 300s stale rule with idle GPU; not a performance number. |

## Boundary Conclusion

The current proven decode boundary is **between 255.25K and 255.375K** for single-request streaming decode with 1024 generated tokens.

The next useful sweep is 255.3125K and 255.34375K. If 255.3125K fails, the boundary is 255.25K-255.3125K. If 255.3125K succeeds and 255.34375K fails, the boundary is 255.3125K-255.34375K. If both succeed, retry 255.375K once more to check whether the stale result is deterministic.

## Data Integrity Note

The 80K metrics are sourced from the per-case serving benchmark log, which emitted a complete `Serving Benchmark Result` block with `Successful requests: 1`. The parent sweep process was interrupted before it appended the 80K row to its outer summary, so the per-case benchmark log is the authoritative source for the 80K metrics.

The earlier 128K stuck note is superseded by the strict rerun. The strict 128K run completed with `Successful requests: 1`, so it is reported as a valid performance number.

The 255.375K result is a strict stale result. It is intentionally not reported as a performance number.

The 255.5K result is also a strict stale result: elapsed time reached 364 seconds, log age reached 316 seconds, GPU utilization remained idle, and the benchmark client was killed. It is intentionally not reported as a performance number.

The 256K result is also a strict stale result: elapsed time reached 364 seconds, log age reached 317 seconds, GPU utilization remained idle, and the benchmark client was killed. It is intentionally not reported as a performance number.
