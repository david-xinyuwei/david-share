# Long-Context Prefill Sweep — 2026-06-18

This sweep tests isolated prefill requests through the EP8/DP1 PD-router stack after the earlier 256K diagnostic showed that repeated 256K traffic can stall.

Raw summary TSV: [`../data/prefill_context_sweep_20260618.tsv`](../data/prefill_context_sweep_20260618.tsv)

## Run Configuration

| Item | Value |
|---|---|
| Topology | 1P+1D PD router, `TP=8`, local `EP=8`, `DP=1` |
| Transfer backend | Mooncake |
| MoE backend | MORI |
| Speculative decode | EAGLE / MTP layer=3 |
| Dataset | random fixed-length prompts, seed `12345` |
| Request shape | `num_prompts=1`, `max_concurrency=1`, `output_len=1` |
| Router handling | router restarted before each isolated case |
| Stale handling | 300 seconds of no log progress plus idle GPU marks a stuck case |

## Results

| Context | Status | Successful requests | Input tok/s | TTFT ms | H200 EP16/DP2 tok/s | MI300X/H200 |
|---:|---|---:|---:|---:|---:|---:|
| 64K | OK | 1 | 10,175.80 | 6,435.04 | 27,400 | 37.1% |
| 128K | OK | 1 | 9,400.48 | 13,938.71 | — | — |
| 192K | OK | 1 | 8,147.34 | 24,127.14 | — | — |
| 256K | OK | 1 | 7,294.02 | 35,934.12 | 17,400 | 41.9% |

## Conclusion

The isolated long-context prefill path works through 256K. Throughput decreases smoothly as context length grows: 10.2K tok/s at 64K, 9.4K at 128K, 8.1K at 192K, and 7.3K at 256K.

This does not remove the earlier 256K serving risk. The repeated/concurrent PD-router path still stalls, but the isolated sweep shows that the long-context prefill compute path itself is viable.

## Evidence Notes

Each case restarted the router before the benchmark request. The raw TSV stores the parsed benchmark metrics. Full per-case logs were retained in the working evidence directory and are summarized here as compact public data.
