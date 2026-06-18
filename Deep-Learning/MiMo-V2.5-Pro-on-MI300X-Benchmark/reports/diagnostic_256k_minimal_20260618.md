# 256K Minimal Diagnostic — 2026-06-18

This diagnostic isolates the 256K-context instability observed in the EP8/DP1 PD-router matrix.

Raw summary TSV: [`../data/diagnostic_256k_minimal_20260618.tsv`](../data/diagnostic_256k_minimal_20260618.tsv)  
Reproduction script: [`../scripts/bench_256k_prefill_minimal.sh`](../scripts/bench_256k_prefill_minimal.sh)

## Purpose

The full matrix showed 256K prefill/decode cases hanging after partial progress. This diagnostic separates three possibilities:

1. The 256K compute path itself cannot run.
2. Streaming response handling causes the hang.
3. Repeated 256K requests leave router / response-drain state that blocks later requests.

## Results

| Case | Status | Successful requests | Input tok/s | TTFT ms | Interpretation |
|---|---|---:|---:|---:|---|
| `prefill_256k_n1_stream` | OK | 1 | 7,196.48 | 36,421.44 | 256K single-request path works. |
| `prefill_256k_n4_nostream_seq` | `EXIT_143` | — | — | — | Sequential `n=4` reached 2/4 then stalled with GPU idle; it was manually killed. |
| `prefill_256k_isolated_restart_2` sample 1 | OK | 1 | 7,281.59 | 35,996.12 | Single request after router restart works. |
| `prefill_256k_isolated_restart_2` sample 2 | OK | 1 | 7,279.81 | 36,004.25 | Single request after router restart works. |
| `prefill_256k_isolated_restart_2` sample 3 | OK | 1 | 7,236.01 | 36,223.07 | Single request after router restart works. |
| `prefill_256k_isolated_restart_2` sample 4 | OK | 1 | 7,201.49 | 36,397.53 | Single request after router restart works. |

Average successful 256K prefill throughput: **7,239.08 input tok/s**.

Compared with the H200 EP16/DP2 256K prefill reference of 17,400 tok/s, the successful single-request MI300X path is **41.6% of H200**.

## Conclusion

The 256K prefill compute path is viable. The failure mode is not a simple compute/OOM failure: repeated 256K requests can stall after partial progress while the router and prefill health checks remain `200`.

The current operational workaround is:

1. Run 256K prefill as isolated single-request measurements.
2. Restart or refresh router state between isolated 256K requests.
3. Treat repeated/concurrent 256K PD-router runs as unstable until the router/Mooncake response-drain path is fixed.

The workaround produces stable single-request numbers around **7.2K tok/s**, but it does not yet solve concurrent 256K serving.

## Evidence Notes

During the failing sequential run, the client stopped at 2/4 requests; GPU utilization dropped to zero and no benchmark metrics were emitted. Router and prefill health checks remained healthy. The case was manually killed to continue isolated tests and is intentionally not reported as a performance number.
