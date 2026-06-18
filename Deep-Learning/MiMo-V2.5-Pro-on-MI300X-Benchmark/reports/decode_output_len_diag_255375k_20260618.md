# Decode Output-Length Diagnostic at 255.375K — 2026-06-18

This diagnostic keeps the target serving protocol unchanged and only changes `random-output-len` at the first failing context boundary.

Raw summary TSV: [`../data/decode_output_len_diag_255375k_20260618.tsv`](../data/decode_output_len_diag_255375k_20260618.tsv)

## Run Configuration

| Item | Value |
|---|---|
| Topology | 1P+1D PD router, `TP=8`, local `EP=8`, `DP=1` |
| Transfer backend | Mooncake |
| MoE backend | MORI |
| Speculative decode | EAGLE / MTP layer=3 |
| Context | 255.375K tokens (`input_len=261504`) |
| Batch | `max_concurrency=1`, `num_prompts=1` |
| Streaming | enabled |
| Router handling | router restarted before each case |
| Stale handling | 300 seconds of no log progress plus idle GPU |

## Results

| Output length | Status | Successful requests | Input tok/s | Output tok/s | TTFT ms | TPOT ms | Interpretation |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | OK | 1 | 7,365.11 | 0.03 | 35,500.74 | 0.00 | Prefill-to-decode handoff is viable. |
| 64 | OK | 1 | 6,777.18 | 1.66 | 34,646.80 | 62.44 | Short decode generation succeeds. |
| 256 | OK | 1 | 5,138.49 | 5.03 | 35,577.77 | 60.03 | Medium decode generation succeeds. |
| 1024 | `STALE_KILLED` | — | — | — | — | — | Long generation / streaming response path stalls. |

## Conclusion

The 255.375K failure is **not** a mandatory prefill-to-decode handoff failure. The same context succeeds with output lengths 1, 64, and 256.

The failure appears when the request must generate 1024 tokens. That points to the long-running decode generation, scheduler state, or streaming response-drain path rather than the initial KV handoff alone.

## Evidence Notes

The 1024-token case hit the strict stale rule: elapsed time reached 364 seconds, log age reached 317 seconds, GPU utilization remained idle, and the benchmark client was killed. Router, prefill, and decode health checks remained healthy after the run.
