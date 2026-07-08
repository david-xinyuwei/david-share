# AMD 2026-07-08 CK A8W8 Concurrency Extension Results

Run ID: `ck_a8w8_concurrency_sweep_20260708_20260708_015402`

Remote evidence root: `/data/xisun/ck_a8w8_concurrency_sweep_20260708_20260708_015402/extension`

Local evidence root: `G:\AI-Super-Agent\x小米H200\reports\20260708-ck-a8w8-concurrency-extension\ck_a8w8_concurrency_sweep_20260708_20260708_015402\extension`

Local archive: `G:\AI-Super-Agent\x小米H200\reports\20260708-ck-a8w8-concurrency-extension\ck_a8w8_concurrency_sweep_20260708_20260708_015402\ck_a8w8_concurrency_sweep_20260708_20260708_015402-extension.tgz`

## Executive Summary

The decode high-concurrency extension completed successfully for all tested concurrency points: 16, 32, 64, 96, 128, 192, and 256. Output throughput saturates around concurrency 64 and then remains flat at roughly 2,200 output tokens/s through concurrency 256.

The prefill concurrency extension completed for 8K and 64K across concurrency 1, 2, 4, and 8. For 256K, concurrency 1 and 2 completed, but concurrency 4 and 8 failed during warmup with `No available prefill workers (all circuits open or unhealthy)`. This means the current CK path supports 256K prefill up to concurrency 2 in this run, but not concurrency 4 or 8 without additional prefill-worker recovery/restart or capacity changes.

## Decode Sweep

Benchmark shape: 8K input, 1K output, `num_prompts=256`, `warmup=32`.

| Concurrency | rc | Successful requests | Output tok/s | Mean TPOT ms | Median TPOT ms | P99 TPOT ms | Mean TTFT ms | P99 TTFT ms |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 0 | 256 | 1321.50 | 10.79 | 10.91 | 11.65 | 1191.13 | 7055.36 |
| 32 | 0 | 256 | 1914.27 | 13.37 | 13.59 | 14.26 | 2847.33 | 14125.62 |
| 64 | 0 | 256 | 2198.77 | 15.49 | 15.93 | 17.08 | 11853.11 | 27631.58 |
| 96 | 0 | 256 | 2200.63 | 15.06 | 15.51 | 16.31 | 23666.92 | 40811.90 |
| 128 | 0 | 256 | 2203.65 | 14.83 | 15.17 | 16.22 | 33429.51 | 54418.65 |
| 192 | 0 | 256 | 2202.57 | 14.72 | 14.90 | 16.28 | 47910.53 | 81273.62 |
| 256 | 0 | 256 | 2207.97 | 14.60 | 14.79 | 16.36 | 55466.82 | 107251.46 |

Decode interpretation:

- Throughput increases from concurrency 16 to 64, then plateaus.
- The plateau is stable: concurrency 64 through 256 stays between `2198.77` and `2207.97` output tok/s.
- Mean TPOT does not degrade after the plateau; it slightly improves from `15.49 ms` at concurrency 64 to `14.60 ms` at concurrency 256.
- Mean and P99 TTFT increase as concurrency increases, which is expected queueing behavior once decode throughput is saturated.

## Prefill Sweep

Benchmark shape: output length 1, `num_prompts=16`, `warmup=1`.

| Input tokens | Concurrency | rc | Successful requests | Input tok/s | Mean TTFT ms | P99 TTFT ms | Observed concurrency |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 8192 | 1 | 0 | 16 | 14811.18 | 552.33 | 589.05 | 1.00 |
| 8192 | 2 | 0 | 16 | 16982.94 | 958.32 | 1368.64 | 1.99 |
| 8192 | 4 | 0 | 16 | 16783.88 | 1840.95 | 2680.40 | 3.77 |
| 8192 | 8 | 0 | 16 | 18617.41 | 3210.75 | 4690.96 | 7.30 |
| 65536 | 1 | 0 | 16 | 16602.69 | 3946.37 | 4869.77 | 1.00 |
| 65536 | 2 | 0 | 16 | 18077.28 | 7122.69 | 9003.76 | 1.96 |
| 65536 | 4 | 0 | 16 | 16904.74 | 14231.93 | 16774.44 | 3.67 |
| 65536 | 8 | 0 | 16 | 17252.39 | 24482.37 | 31726.89 | 6.45 |
| 262144 | 1 | 0 | 16 | 35452.56 | 6995.06 | 22647.57 | 1.00 |
| 262144 | 2 | 0 | 16 | 37429.63 | 12417.08 | 47335.03 | 1.83 |
| 262144 | 4 | 1 | NA | NA | NA | NA | NA |
| 262144 | 8 | 1 | NA | NA | NA | NA | NA |

Prefill interpretation:

- 8K prefill scales through concurrency 8 in this matrix, with best observed throughput `18617.41` input tok/s at concurrency 8.
- 64K prefill is best at concurrency 2 (`18077.28` input tok/s), with concurrency 4/8 still successful but not materially higher.
- 256K prefill is best at concurrency 2 (`37429.63` input tok/s), but concurrency 4 and 8 fail before measurement during warmup.
- The 256K/con4 and 256K/con8 failures share the same failure signature: router is ready, but warmup cannot select a healthy prefill worker.

## Failure Signature

256K/con4 and 256K/con8 both failed with:

```text
ValueError: Warmup failed - Please make sure benchmark arguments are correctly specified.
Error: Service Unavailable: {"error":{"type":"Service Unavailable","code":"server_selection_failed","message":"No available servers: No available prefill workers (all circuits open or unhealthy)"}}
```

The failure happens after `/v1/models` reports ready and before benchmark measurement begins:

```text
Waiting up to 60s for http://0.0.0.0:40000/v1/models to become ready...
Server ready in 0.0s.
#Input tokens: 4194304
#Output tokens: 16
Starting warmup with 1 sequences...
```

This should be reported as a 256K high-prefill-concurrency availability boundary, not as a measured throughput regression.

## Run Exit Status

| Component | rc | Notes |
|---|---:|---|
| Decode sweep | 0 | All decode concurrency points completed successfully. |
| Prefill sweep | 1 | Matrix-level rc is 1 because 256K/con4 and 256K/con8 failed during warmup. Successful rows remain valid. |

Error marker count from final remote check:

| Area | Count |
|---|---:|
| Decode | 0 |
| Prefill | 12 |

## Evidence Files

Key local files:

- `extension/decode/summary.tsv`
- `extension/prefill/summary.tsv`
- `extension/decode_full.rc`
- `extension/prefill_full.rc`
- `extension/prefill/prefill_262144_out1_con4.log`
- `extension/prefill/prefill_262144_out1_con8.log`

The full pulled artifact contains 44 files under `extension/` and was verified locally after extraction.
