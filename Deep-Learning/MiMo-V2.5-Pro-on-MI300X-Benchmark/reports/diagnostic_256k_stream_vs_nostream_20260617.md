# 256K Long-Context Diagnostic — Stream vs No-Stream

Generated: 2026-06-17

## Result

Both 256K single-request tests completed successfully through the PD router.

| Case | Input | Output | BS | Prompts | Streaming | Success | Input tok/s | TTFT |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| stream_on | 262144 | 1 | 1 | 1 | on | 1/1 | 7315.27 | 35830.22 ms |
| disable_stream | 262144 | 1 | 1 | 1 | off | 1/1 | 7251.86 | 36143.90 ms |

## Interpretation

256K is not fundamentally impossible on the current MI300X PD+MTP stack. A single 256K request can complete in about 36 seconds.

The failure boundary is repeated or concurrent 256K requests through the PD router path. The monolithic matrix and micro-matrix both failed when multiple 256K requests were issued, showing `ClientPayloadError: Response payload is not completed` on the client and `Error consuming prefill response: error decoding response body` in the router.

Because both streaming and no-stream single-request tests succeeded, streaming alone is not the root cause. The issue is more likely in the long-context PD router/prefill response drain or request lifecycle under repeated/concurrent load.

## Evidence

- Workspace diagnostic logs: `G:\AI-Super-Agent\x小米H200\reports\mi300x-256k-diagnostic-20260617\`
- Parsed TSV: `data/diagnostic_256k_stream_vs_nostream_20260617.tsv`
