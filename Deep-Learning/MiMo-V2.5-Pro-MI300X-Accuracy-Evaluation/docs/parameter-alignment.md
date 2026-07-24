# H200 Reference vs AMD MI300X Parameter Alignment

This document maps the provided H200 reference launch method to the MI300X runtime used by this accuracy snapshot. “Aligned” means the option and value match. “Topology adaptation” and “backend substitution” are disclosed differences, not silently normalized away.

## Summary

- H200 reference: TP16 / DP2 / EP16 / PP1 with DP Attention and FA3.
- MI300X measurement: two independent services, each TP8 / DP1 / EP1 / PP1 with AITER.
- FP8, page size, context length, request ceiling, EAGLE controls, parsers, model loader, metrics, and histogram buckets are aligned.
- Cross-node parameters do not apply to the two independent MI300X services.
- Accuracy sampling and scoring are evaluator-owned and are unchanged by the serving topology adaptation.

## Launch Parameter Matrix

| # | H200 reference | MI300X measured setting | Status | Rationale |
|---:|---|---|---|---|
| 1 | `python3 -m sglang.launch_server` | `python3 -u -m sglang.launch_server` | Equivalent | `-u` only makes logs unbuffered. |
| 2 | Reference model path | Local MiMo-V2.5-Pro model path | Environment adaptation | Paths are deployment-specific and are not published. |
| 3 | `--trust-remote-code` | Same | Aligned | — |
| 4 | `--pp-size 1` | `--pp-size 1` | Aligned | — |
| 5 | `--dp-size 2` | `--dp-size 1` | Topology adaptation | Each MI300X node runs one independent service. |
| 6 | `--ep-size 16` | `--ep-size 1` | Topology adaptation | The measured stable MI300X path uses EP1. |
| 7 | `--tp-size 16` | `--tp-size 8` | Topology adaptation | Each service uses all eight local MI300X GPUs. |
| 8 | `--moe-dense-tp-size 1` | Same | Aligned | — |
| 9 | `--enable-dp-attention` | Not set | Not applicable | DP Attention is not enabled at DP1. |
| 10 | `--dist-init-addr ...` | Not set | Not applicable | Independent single-node services do not form a cross-node group. |
| 11 | `--node-rank ...` | Not set | Not applicable | — |
| 12 | `--nnodes ...` | Not set | Not applicable | — |
| 13 | `--page-size 1` | Same | Aligned | — |
| 14 | `--attention-backend fa3` | `--attention-backend aiter` | Backend substitution | FA3 targets NVIDIA Hopper; MI300X uses AMD AITER. |
| 15 | `--quantization fp8` | Same | Aligned | — |
| 16 | `--mem-fraction-static 0.8` | Same | Aligned | — |
| 17 | `--max-running-requests 128` | Same | Aligned | — |
| 18 | `--context-length 1048576` | Same | Aligned | — |
| 19 | `--tokenizer-worker-num 64` | Same | Aligned | — |
| 20 | `--speculative-algorithm EAGLE` | Same | Aligned | — |
| 21 | `--speculative-num-steps 3` | Same | Aligned | — |
| 22 | `--speculative-eagle-topk 1` | Same | Aligned | — |
| 23 | `--speculative-num-draft-tokens 4` | Same | Aligned | — |
| 24 | `--enable-multi-layer-eagle` | Same | Aligned | — |
| 25 | `--host 0.0.0.0` | Node-local accelerator-network address | Network adaptation | Internal addresses are not published. |
| 26 | Reference port | Deployment-local port | Network adaptation | Port choice does not change sampling or scoring. |
| 27 | `--reasoning-parser qwen3` | Same | Aligned | — |
| 28 | `--tool-call-parser mimo` | Same | Aligned | — |
| 29 | `--watchdog-timeout 3600` | Same | Aligned | — |
| 30 | Multithread model load, 64 threads | Same | Aligned | — |
| 31 | `--log-level-http warning` | Same | Aligned | — |
| 32 | `--enable-cache-report` | Same | Aligned | Observability only. |
| 33 | `--collect-tokens-histogram` | Same | Aligned | Observability only. |
| 34 | `--enable-metrics` | Same | Aligned | Observability only. |
| 35 | TTFT buckets: `0.1 ... 7200` | Same 24-value sequence | Aligned | Observability only. |
| 36 | E2E latency buckets: `0.1 ... 7200` | Same 24-value sequence | Aligned | Observability only. |
| 37 | `--decode-log-interval 1` | Same | Aligned | Observability only. |
| 38 | `--enable-metrics-for-all-schedulers` | Same | Aligned | Observability only. |
| 39 | `SGLANG_ENABLE_SPEC_V2=1` | Same | Aligned | Verified in the measured runtime. |

## AMD Runtime Controls

| Control | Value | Purpose |
|---|---|---|
| `SGLANG_USE_AITER` | `1` | Enable the AMD AITER kernel path. |
| `SGLANG_MOE_PADDING` | `1` | Enable the measured AMD MoE padding path. |
| `SGLANG_ROCM_FUSED_DECODE_MLA` | `1` | Enable ROCm fused decode MLA. |
| `SGLANG_SET_CPU_AFFINITY` | `1` | Stabilize process placement. |
| `HSA_NO_SCRATCH_RECLAIM` | `1` | Fix HSA scratch behavior for the measured runtime. |
| `SGLANG_SPEC_NAN_DETECTION` | `1` | Fail closed on speculative-decoding NaNs. |
| `SGLANG_SPEC_OOB_DETECTION` | `1` | Detect speculative-decoding out-of-bounds conditions. |
| `SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE` | `1` | Enable the validated block-scale B-preshuffle path. |
| Simulated acceptance variables | Not set | Accuracy uses natural EAGLE acceptance. |

## Comparability Boundary

The mapping aligns the model, quantization, sampling contract, speculative-decoding controls, context length, and scoring path. It does **not** make TP8/DP1/EP1/AITER equivalent to TP16/DP2/EP16/FA3 for performance or communication behavior. Accuracy differences remain directional until full, matched raw outputs are available on both hardware paths.
