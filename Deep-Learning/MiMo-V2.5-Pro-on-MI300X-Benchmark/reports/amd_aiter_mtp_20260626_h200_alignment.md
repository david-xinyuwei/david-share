# 2026-06-26 AMD aiter+MTP3 vs H200 Alignment

Source scope: MI300X numbers are parsed from raw 2026-06-26 logs copied under `data/raw-logs/20260626-amd-aiter-mtp/`; H200 numbers are transcribed from `G:/AI-Super-Agent/x小米H200/20260626 AMD更新/H200测试结果.png`.

## Bottom Line

- Prefill, against the H200 EP16/DP2 prefill reference: MI300X is 0.51x at 8K and 0.55x at 64K, so H200 is about 1.8-2.0x faster on the common short/medium context points. The 256K row flips: MI300X is 2.14x H200, but this should be treated as a specific 6/26 long-context run because the prior repo history had 256K router-drain instability.
- Decode 8K/1K, same visible BS rows from the 6/26 H200 sheet: H200 output throughput is 2.0x faster at BS16, 2.5x at BS32, 3.2x at BS64, and 5.0x at BS128. MI300X latency is 1.9-2.4x slower on TPOT.
- The H200 decode sheet labels `bs (per DP)` with `dp size=4`, but its throughput column equals `BS * 1000 / TPOT`, not `BS * DP * 1000 / TPOT`. The main decode comparison therefore uses the sheet-provided throughput column and calls it a visible-BS-row comparison.

## Prefill Throughput

| Input | MI300X tok/s | H200 EP16/DP2 tok/s | MI/H200 | H200 faster | H200 EP32/DP4 tok/s | MI/H200 | H200 faster |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 8,192 | 16,323.45 | 31,950 | 51.1% | 1.96x | 27,500 | 59.4% | 1.68x |
| 65,536 | 15,047.08 | 27,400 | 54.9% | 1.82x | 23,000 | 65.4% | 1.53x |
| 262,144 | 37,251.55 | 17,400 | 214.1% | 0.47x | 13,425 | 277.5% | 0.36x |

## Decode 8K/1K

| BS row | MI300X TPOT ms | H200 TPOT ms | MI latency slower | MI300X output tok/s | H200 output tok/s | MI/H200 throughput | H200 faster | MI accept len/rate | H200 accept rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 21.61 | 11.59 | 1.86x | 689.22 | 1,380.71 | 49.9% | 2.00x | 2.38/0.46 | 0.75 |
| 32 | 27.94 | 12.56 | 2.22x | 1,017.58 | 2,548.66 | 39.9% | 2.50x | 2.34/0.44 | 0.75 |
| 64 | 34.78 | 14.28 | 2.44x | 1,391.54 | 4,482.93 | 31.0% | 3.22x | 2.25/0.41 | 0.75 |
| 128 | 34.70 | 18.25 | 1.90x | 1,396.29 | 7,013.05 | 19.9% | 5.02x | 2.15/0.38 | 0.75 |

## Raw Evidence

- `data/raw-logs/20260626-amd-aiter-mtp/benchmark_8192_con128.txt`
- `data/raw-logs/20260626-amd-aiter-mtp/benchmark_8192_con16.txt`
- `data/raw-logs/20260626-amd-aiter-mtp/benchmark_8192_con32.txt`
- `data/raw-logs/20260626-amd-aiter-mtp/benchmark_8192_con64.txt`
- `data/raw-logs/20260626-amd-aiter-mtp/decode_benchmark_8192_con1.txt`
- `data/raw-logs/20260626-amd-aiter-mtp/prefill_benchmark_262144_con4.txt`
- `data/raw-logs/20260626-amd-aiter-mtp/prefill_benchmark_65536_con4.txt`
- `data/raw-logs/20260626-amd-aiter-mtp/prefill_benchmark_8192_con4.txt`
- `data/amd_aiter_mtp_20260626_h200_alignment.tsv`
