# AMD Tuned MoE Retest — tuned_moe_retest_20260713T014113Z

## Decode

| Concurrency | Success | Output tok/s | Mean TPOT ms | Output vs strict baseline | TPOT vs strict baseline | Errors |
|---|---|---|---|---|---|---|
| 16 | 256 | 1331.98 | 10.83 | +2.52% | +1.79% | 0 |
| 32 | 256 | 1936.24 | 13.65 | +1.33% | +1.11% | 0 |
| 64 | 256 | 2457.73 | 17.00 | +12.33% | +12.58% | 0 |
| 128 | 256 | 2486.89 | 16.56 | +12.56% | +14.05% | 0 |

## 1P1D Prefill

| Input tokens | Concurrency | Success | Input tok/s | vs strict baseline | vs H200 | Errors |
|---|---|---|---|---|---|---|
| 8192 | 4 | 16 | 20780.79 | +24.32% | 65.0% | 0 |
| 65536 | 4 | 16 | 19022.57 | +10.25% | 69.4% | 0 |
| 262144 | 4 | 16 | EXCLUDED | EXCLUDED | EXCLUDED | SERVER OVERFLOW |

## DP=2 Prefill

| Input tokens | Concurrency | Success | Aggregate tok/s | Per-node tok/s | Per-node vs H200 | Errors |
|---|---|---|---|---|---|---|
| 8192 | 4 | 32 | 43221.12 | 21610.56 | 67.6% | 0 |
| 8192 | 8 | 32 | 45992.94 | 22996.47 | 72.0% | 0 |
| 65536 | 4 | 32 | 38374.65 | 19187.33 | 70.0% | 0 |
| 65536 | 8 | 32 | 38255.28 | 19127.64 | 69.8% | 0 |
| 262144 | 4 | 32 | 74611.25 | 37305.62 | 214.4% | 0 |
| 262144 | 8 | 32 | 78613.96 | 39306.98 | 225.9% | 0 |

## DP=2 256K Correctness Guard

- The supplied `--context-length 262144` setting was insufficient for the standard DP=2 server path: a requested 262,144-token random input became 262,148 server-side tokens, and HTTP 200 error payloads could still appear as successful client responses.
- The invalid attempt is excluded; its deterministic overflow counts are recorded in `checks/validation.txt`.
- The accepted rerun kept `random_input_len=262144` and `random_output_len=1`, while setting the server allowance to 262,149 tokens. Both node service logs report zero context-overflow errors for the final six-point matrix.

## 1P1D 256K Erratum

- The original 1P1D 256K client summary is excluded. Node 0 and node 1 each logged 11 context-overflow responses while the client still reported 16 successful requests.
- The published 1P1D launch scripts now use a 262,149-token server allowance. A corrected rerun is required before publishing 1P1D 256K throughput.

## Interpretation

- Decode high-concurrency output throughput is the primary tuned-MoE gain; report TPOT separately because BS64/128 trade throughput for higher TPOT.
- Validated 1P1D Prefill gains are positive at 8K and 64K; the original 256K point is excluded.
- DP=2 results are prefill-only server-mode measurements and do not include P→D KV transfer.
- The single-kernel 37.6% latency reduction is AMD-reported; no standalone microbenchmark log was provided in the shared evidence directory.
