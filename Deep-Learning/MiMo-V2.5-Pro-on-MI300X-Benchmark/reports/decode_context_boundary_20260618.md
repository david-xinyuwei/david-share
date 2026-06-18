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
| Stale handling | stuck cases were identified by 0/1 benchmark progress, GPU idle, and healthy router/prefill/decode checks |

## Results

| Context | Status | Successful requests | Input tok/s | Output tok/s | TTFT ms | TPOT ms | Interpretation |
|---:|---|---:|---:|---:|---:|---:|---|
| 64K | OK | 1 | 2,191.78 | 34.25 | 6,340.27 | 23.03 | Baseline long-context decode succeeds. |
| 80K | OK | 1 | 2,361.72 | 29.52 | 8,011.51 | 26.07 | First refined boundary point succeeds. |
| 128K | `MANUAL_STUCK_0_OF_1_GPU0_HEALTH200` | — | — | — | — | — | Request stayed at 0/1 with idle GPU and healthy endpoints. |

## Boundary Conclusion

The current proven decode boundary is **above 80K and at or below 128K** for single-request streaming decode with 1024 generated tokens.

The next useful sweep is 96K and 112K. A successful 96K and failed 112K would narrow the boundary to 96K-112K; a successful 112K and failed 128K would narrow it to 112K-128K.

## Data Integrity Note

The 80K metrics are sourced from the per-case serving benchmark log, which emitted a complete `Serving Benchmark Result` block with `Successful requests: 1`. The parent sweep process was interrupted before it appended the 80K row to its outer summary, so the per-case benchmark log is the authoritative source for the 80K metrics.

The 128K stuck result is sourced from the stream sweep result log: the request remained at 0/1, GPU utilization was idle, and router, prefill, and decode health checks all returned healthy status. It is intentionally not reported as a performance number.
