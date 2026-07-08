# AMD 2026-07-07 CK GEMM Strict Reproduction Results

Date: 2026-07-07
Evidence root: `data/raw-logs/20260707-ck-a8w8-gemm/`

## Scope

This run follows AMD's original 2026-07-07 reproduction steps. The exact launch and benchmark scripts used in this strict pass are archived under `scripts/20260707-amd-ck-a8w8/`.

The only execution-carrier adaptation was to keep the foreground services in separate sessions:

- Prefill server: `./launch_tp8_noep_prefill_aiter_mtp.sh`
- Decode server: `./launch_tp8_noep_decode_aiter_mtp.sh`
- Router: `./launch_router.sh`
- Benchmarks: `./run_benchmark_mimo_pro_decode.sh`, then `./run_benchmark_mimo_pro_prefill.sh`

No AMD scripts were edited for this strict pass.

## AMD Script Parameters Observed

Source: read-only grep of `/data/xisun/*.sh` inside the AMD `sglang` container on the prefill node.

- Prefill launch enables `SGLANG_USE_AITER=1`.
- Prefill launch enables `SGLANG_SIMULATE_ACC_LEN=3` and `SGLANG_SIMULATE_ACC_METHOD=match-expected`.
- Prefill launch enables `SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1`.
- Prefill launch uses `--max-running-requests 128`, `--chunked-prefill-size 32768`, `--page-size 32`, and `--disaggregation-mode prefill`.
- Decode launch uses `--max-running-requests 128`, `--chunked-prefill-size 16384`, and `--disaggregation-mode decode`.
- Decode benchmark uses 8K/1K with target concurrency 16/32/64/128, `--num-prompts 256`, `--warmup-requests 32`, `--flush-cache`, and `--pd-separated`.
- Prefill benchmark uses 8K/1, 64K/1, 256K/1 with target concurrency 4, `--num-prompts 16`, `--warmup-requests 1`, `--flush-cache`, and `--pd-separated`.

## Completion And Error Scan

Source files:

- `remote-prefill/bench/decode_full.out`
- `remote-prefill/bench/decode_full.rc`
- `remote-prefill/bench/prefill_full.out`
- `remote-prefill/bench/prefill_full.rc`

Results:

- `decode_full.rc = 0`
- `prefill_full.rc = 0`
- Benchmark output scan found no `ClientPayloadError`, `Traceback`, `Exception`, `ERROR`, `No available`, `unhealthy`, or `TimedOut` markers.
- Router log showed transient `/health` timeout warnings during the long 64K prefill phase, while `/generate` requests continued returning HTTP 200. Treat this as a runtime caveat, not a benchmark-script failure.

## Decode Results

Workload: 8K/1K decode, target concurrency 16/32/64/128, 256 prompts per point.

| ISL/OSL | Target concurrency | Successful requests | Output tok/s | Mean TPOT ms | Median TPOT ms | P99 TPOT ms | Mean TTFT ms | P99 TTFT ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 8K/1K | 16 | 256 | 1299.18 | 10.64 | 10.83 | 11.57 | 1440.59 | 7000.93 |
| 8K/1K | 32 | 256 | 1910.75 | 13.50 | 13.73 | 14.25 | 2736.20 | 14607.56 |
| 8K/1K | 64 | 256 | 2188.05 | 15.10 | 15.53 | 16.58 | 12290.37 | 27089.19 |
| 8K/1K | 128 | 256 | 2209.43 | 14.52 | 14.83 | 15.82 | 33480.37 | 53818.14 |

## Decode Comparison Against AMD 2026-07-07 CK Row

AMD CK row source: AMD-provided 2026-07-07 result table.

| BS | AMD CK TPOT ms | Repro mean TPOT ms | Delta | AMD CK output tok/s | Repro output tok/s | Delta |
|---:|---:|---:|---:|---:|---:|---:|
| 16 | 10.59 | 10.64 | +0.05 ms / +0.5% | 1305.03 | 1299.18 | -5.85 / -0.4% |
| 32 | 13.43 | 13.50 | +0.07 ms / +0.5% | 1910.16 | 1910.75 | +0.59 / +0.0% |
| 64 | 14.92 | 15.10 | +0.18 ms / +1.2% | 2185.63 | 2188.05 | +2.42 / +0.1% |
| 128 | 14.55 | 14.52 | -0.03 ms / -0.2% | 2203.83 | 2209.43 | +5.60 / +0.3% |

Interpretation: the strict reproduction matches AMD's 2026-07-07 CK decode table within about 1.2% on mean TPOT and within about 0.4% on output throughput.

## Prefill Results

Workload: 8K/1, 64K/1, 256K/1 prefill, target concurrency 4, 16 prompts per point.

| ISL/OSL | Target concurrency | Successful requests | Input tok/s | Mean TTFT ms | P99 TTFT ms | Observed concurrency |
|---|---:|---:|---:|---:|---:|---:|
| 8K/1 | 4 | 16 | 16715.80 | 1849.62 | 2709.97 | 3.77 |
| 64K/1 | 4 | 16 | 17254.14 | 14107.62 | 16674.08 | 3.71 |
| 256K/1 | 4 | 16 | 37492.80 | 19278.17 | 86264.51 | 2.88 |

## Prefill Comparison Notes

The observed prefill launch uses `--chunked-prefill-size 32768`, even though the log filename says `chunk_128k`. Therefore the cleanest table comparison is against AMD's CK 32K chunk column where available:

| ISL/OSL | AMD CK 32K input tok/s | Repro input tok/s | Delta |
|---:|---:|---:|---:|
| 8K/1 | 16924.08 | 16715.80 | -208.28 / -1.2% |
| 64K/1 | 17223.51 | 17254.14 | +30.63 / +0.2% |
| 256K/1 | 37241.84 | 37492.80 | +250.96 / +0.7% |

Interpretation: the strict reproduction also matches the CK 32K prefill column closely, within about 1.2% across 8K/64K/256K.

## Evidence Files

Repo evidence root:

`data/raw-logs/20260707-ck-a8w8-gemm/`

Key files:

- `remote-prefill/bench/decode_full.out`
- `remote-prefill/bench/decode_full.rc`
- `remote-prefill/bench/prefill_full.out`
- `remote-prefill/bench/prefill_full.rc`
- `remote-prefill/env/script_sha256.txt`
- `remote-prefill/env/rdma_gate.txt`
- `remote-prefill/env/python_imports.txt`
- `remote-prefill/env/docker_inspect_sglang.json`
- `remote-decode/summary/status_decode.txt`
- `remote-prefill/summary/status_prefill.txt`

## Bottom Line

Strict AMD-step reproduction passed.

- Decode: 4/4 concurrency points completed, all 256/256 successful, `rc=0`, no benchmark error markers.
- Prefill: 3/3 input lengths completed, all 16/16 successful, `rc=0`, no benchmark error markers.
- Decode matches AMD's CK 2026-07-07 row within about 1.2% TPOT and about 0.4% output throughput.
- Prefill matches the script-observed CK 32K chunk column within about 1.2% input throughput.
- Caveat: router emitted transient health timeout warnings during long 64K prefill, but benchmark outputs completed successfully.