# Valid July 13 Tuned-MoE Reproduction and 256K Context Fix

This report reconciles the July 7 CK A8W8 reproduction, the July 13 tuned-MoE update, and the corrected 1P1D 256K/concurrency-4 result. All percentage changes below use independently measured valid points; they are separate fresh-service runs, not a same-process paired A/B.

## Best Observed Valid Headline Values

The table below selects the highest accepted measurement at each matching AMD headline workload. It is a cross-run best-observed view with explicit provenance, not a same-session paired matrix.

| Surface | Workload | Best MI300X tok/s | AMD tok/s | Delta | Evidence phase |
|---|---|---:|---:|---:|---|
| Decode | 8K/1K, c16 | 1,331.98 | 1,394.70 | -4.50% | Fresh-service repeat 1 |
| Decode | 8K/1K, c32 | 1,936.24 | 2,042.42 | -5.20% | Fresh-service repeat 1 |
| Decode | 8K/1K, c64 | 2,465.01 | 2,454.64 | +0.42% | Checksum-locked on-node scripts |
| Decode | 8K/1K, c128 | 2,486.89 | 2,473.74 | +0.53% | Fresh-service repeat 1 |
| 1P1D Prefill | 8K/1, c4 | 20,305.98 | 20,689.70 | -1.85% | AMD exact-script reproduction |
| 1P1D Prefill | 64K/1, c4 | 18,983.91 | 18,689.51 | +1.58% | Checksum-locked on-node scripts |
| 1P1D Prefill | 256K/1, c4 | 12,864.96 | 39,279.65 | Not comparable | Exact-token corrected run; supplier row lacks validity evidence |

Selection requires the expected response and retokenized-output counts, direct worker capacity, and zero fatal/context markers. The canonical single-full matrix remains the primary robustness artifact.

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

The original AMD launch scripts set `--context-length 262144` while the benchmark sends a 262,144-token prompt with EAGLE enabled. In the latest checksum-locked on-node reproduction, the client printed:

```text
Successful requests:                     16
Total input tokens:                      4194304
Total generated tokens (retokenized):    5
Input token throughput (tok/s):          39627.96
```

Only `5/16` requests therefore produced a retokenized output. The Prefill and Decode service logs recorded eleven matching errors:

```text
[http_server] Error: The input (262148 tokens) is longer than the model's context length (262144 tokens).
```

The 262,148-token validation value is the 262,144-token prompt plus four EAGLE-reserved draft slots, not four tokenizer special tokens. Those HTTP 200 error payloads were counted as successful requests and as full inputs while returning before completing the work. The resulting `39,627.96 tok/s` is therefore a false-success metric. AMD did not provide the raw client and service logs for its screenshot row, so this report does not assert the exact failure count in AMD's run; it demonstrates that the supplied scripts reproduce the same numeric range through an invalid path in this runtime.

## Corrected 256K Confirmations

The minimum server-side correction is applied on both workers:

```diff
-  --context-length 262144
+  --context-length 262151
```

Two accepted confirmations are retained. The earlier service-only run kept the historical text client. The latest run additionally used `--tokenize-prompt`, sending exactly 262,144 token IDs per request and removing text decode/re-encode drift.

| Evidence | Service-only confirmation | Exact-token confirmation |
|---|---:|---:|
| Prefill `context_length` / `max_req_input_len` | 262151 / 262145 | 262151 / 262145 |
| Decode `context_length` / `max_req_input_len` | 262151 / 262145 | 262151 / 262145 |
| Successful requests | 16/16 | 16/16 |
| Retokenized outputs | 16/16 | 16/16 |
| Accounted input tokens | 4,194,304 | 4,194,304 |
| Benchmark duration | 338.44 s | 326.03 s |
| Valid input throughput | 12,393.19 tok/s | **12,864.96 tok/s** |
| Client input mode | Text decode/re-encode | Exact token IDs (`--tokenize-prompt`) |
| Context overflow / fatal markers | 0 | 0 |

The full-matrix 256K/c4 result was 12,389.64 tok/s. The exact-token confirmation is 3.84% higher and is the current best observed valid c4 value. The two client representations are reported separately rather than treated as strict repeatability samples.

## Public Evidence

- Structured comparison: [`../data/20260714-valid-reproduction-summary.tsv`](../data/20260714-valid-reproduction-summary.tsv)
- Best-observed structured summary: [`../data/20260714-best-observed-valid.tsv`](../data/20260714-best-observed-valid.tsv)
- Sanitized client and service excerpts: [`../data/raw-logs/20260714-valid-256k-context-fix/`](../data/raw-logs/20260714-valid-256k-context-fix/)
- Latest exact-token and checksum-locked on-node evidence: [`../data/raw-logs/20260714-exact-token-and-onnode/`](../data/raw-logs/20260714-exact-token-and-onnode/)
- Exact-token reproduction bundle: [`../scripts/20260714-exact-token-256k/`](../scripts/20260714-exact-token-256k/)
- Expanded matrix: [`20260713-amd-tuned-moe-expanded-concurrency.md`](20260713-amd-tuned-moe-expanded-concurrency.md)
- July 7 strict reproduction: [`20260707-ck-a8w8-gemm-strict-repro.md`](20260707-ck-a8w8-gemm-strict-repro.md)