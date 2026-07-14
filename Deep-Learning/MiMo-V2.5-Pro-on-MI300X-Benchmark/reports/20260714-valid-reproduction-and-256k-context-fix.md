# Valid July 13 Tuned-MoE Reproduction and 256K Context Fix

This report reconciles the July 7 CK A8W8 reproduction, the July 13 tuned-MoE update, and the corrected 1P1D 256K/concurrency-4 result. All percentage changes below use independently measured valid points; they are separate fresh-service runs, not a same-process paired A/B.

## Valid July 7 CK to July 13 Tuned-MoE Comparison

| Surface | Workload | July 7 CK tok/s | July 13 tuned tok/s | Change | Validity |
|---|---|---:|---:|---:|---|
| Decode | 8K/1K, c16 | 1,299.18 | 1,303.44 | +0.33% | 256/256 both runs |
| Decode | 8K/1K, c32 | 1,910.75 | 1,930.10 | +1.01% | 256/256 both runs |
| Decode | 8K/1K, c64 | 2,188.05 | 2,462.83 | +12.56% | 256/256 both runs |
| Decode | 8K/1K, c128 | 2,209.43 | 2,468.95 | +11.75% | 256/256 both runs |
| 1P1D Prefill | 8K/1, c4 | 16,715.80 | 20,305.98 | +21.48% | 16/16 both runs |
| 1P1D Prefill | 64K/1, c4 | 17,254.14 | 18,694.26 | +8.35% | 16/16 both runs |

The tuned-MoE configuration therefore shows material valid gains at 8K/64K Prefill and medium/high Decode concurrency. The low Decode concurrencies show smaller positive changes. The public `aiter@d725746` change selects model/workload-specific fused-MoE configurations; it does not introduce a new fused-MoE kernel implementation.

## Why the Original 256K Number Is Rejected

The original AMD launch scripts set `--context-length 262144` while the benchmark sends a 262,144-token prompt with MTP enabled. In our same-script reproduction, the client printed:

```text
Successful requests:                     16
Total input tokens:                      4194304
Total generated tokens (retokenized):    5
Input token throughput (tok/s):          39905.41
```

Only `5/16` requests therefore produced a retokenized output. The Prefill and Decode service logs recorded eleven matching errors:

```text
[http_server] Error: The input (262148 tokens) is longer than the model's context length (262144 tokens).
```

Those HTTP 200 error payloads were counted as successful requests and as full 262,144-token inputs, while they returned before completing the work. The resulting `39,905.41 tok/s` is therefore a false-success metric. AMD did not provide the raw client and service logs for its screenshot row, so this report does not assert the exact failure count in AMD's run; it demonstrates that the supplied script reproduces the same numeric range through an invalid path.

## Minimal Valid Fix and Result

Only the Prefill and Decode server allowance changed:

```diff
-  --context-length 262144
+  --context-length 262151
```

The client workload remained unchanged: 262,144 input tokens, output length 1, concurrency 4, 16 prompts, one warmup, `--flush-cache`, seed 12345, and `--pd-separated`.

| Evidence | Result |
|---|---:|
| Prefill `context_length` / `max_req_input_len` | 262151 / 262145 |
| Decode `context_length` / `max_req_input_len` | 262151 / 262145 |
| Successful requests | 16/16 |
| Retokenized outputs | 16/16 |
| Accounted input tokens | 4,194,304 |
| Benchmark duration | 338.44 s |
| Valid input throughput | **12,393.19 tok/s** |
| Context overflow / fatal markers | 0 |

The full-matrix 256K/c4 result was 12,389.64 tok/s. The independent context-fix confirmation is 12,393.19 tok/s, a difference of only +0.03%. Raising the server allowance by seven tokens did not cause a measurable throughput regression.

## Public Evidence

- Structured comparison: [`../data/20260714-valid-reproduction-summary.tsv`](../data/20260714-valid-reproduction-summary.tsv)
- Sanitized client and service excerpts: [`../data/raw-logs/20260714-valid-256k-context-fix/`](../data/raw-logs/20260714-valid-256k-context-fix/)
- Expanded matrix: [`20260713-amd-tuned-moe-expanded-concurrency.md`](20260713-amd-tuned-moe-expanded-concurrency.md)
- July 7 strict reproduction: [`20260707-ck-a8w8-gemm-strict-repro.md`](20260707-ck-a8w8-gemm-strict-repro.md)