# TP16 / DP2 DP-Attention Topology Probe

Generated: 2026-06-17

Status: FAILED_BEFORE_READY

This report records the first attempt to express Xiaomi's H200 prefill topology on the Azure MI300X test pair using a two-node SGLang server.

## Why This Probe Exists

The H200 reference sheet uses:

```text
global ep_size = attn_tp_size * dp_size
```

For the first H200 prefill group:

| Field | Value |
|-------|------:|
| attn TP size | 8 |
| DP size | 2 |
| global EP size | 16 |
| chunk size per DP | 16384 |

The completed MI300X baseline is `TP=8, local EP=8, DP=1`. That is a valid workload-shape comparison, but it is not the same topology as H200.

## Corrected SGLang Mapping

For `MiMoV2ForCausalLM` with fused QKV, the current AMD SGLang fork validates effective attention TP as:

```text
effective_attn_tp_size = tp_size / dp_size / attn_cp_size
expected_effective_attn_tp = num_key_value_heads = 8
```

Therefore the tested mapping was:

```bash
--tp-size 16 \
--dp-size 2 \
--enable-dp-attention \
--enable-dp-lm-head
```

This gives:

```text
effective_attn_tp_size = 16 / 2 = 8
```

That is the closest current SGLang expression of H200 prefill `attn TP=8, DP=2, global EP=16` for MiMo-V2.5-Pro.

## Launch Scripts

- Node 0: [`scripts/launch_tp16_dp2_node0.sh`](../scripts/launch_tp16_dp2_node0.sh)
- Node 1: [`scripts/launch_tp16_dp2_node1.sh`](../scripts/launch_tp16_dp2_node1.sh)

Both scripts use environment variables for node addressing. They intentionally avoid hard-coding VM public IPs or credentials.

## Result

The server did not reach readiness.

| Check | Result |
|-------|--------|
| Model/config argument validation | Passed far enough to emit full `server_args` |
| Effective attention TP mismatch | Not observed |
| Server ready marker | `0` occurrences of `fired up` on both nodes |
| Failure class | MORI dispatch/combine heap pressure plus HIP invalid argument |
| Node 1 final symptom | Runtime engine did not initialize; FastAPI lifespan later saw `NoneType.server_args` |

Representative sanitized log excerpt:

```text
Out of heap memory! Requested roughly 822 MB while current heap was 4 GB.
hip failed with invalid argument in dispatch_combine.cpp:150.
NCCL/RCCL all-reduce warnings appeared around the same failure window.
```

## Interpretation

This is a useful negative result:

1. The corrected topology expression (`TP16/DP2 with DP attention`) is not rejected by the MiMo-V2.5-Pro fused-QKV effective-TP check.
2. The failure appears later, in distributed expert dispatch / MORI heap allocation, before the HTTP server becomes ready.
3. Because the server never became ready, there are no TP16/DP2 throughput or TPOT numbers.

## Next Technical Questions

For AMD / SGLang follow-up:

1. What MORI heap and preallocation knobs are recommended for a 16-rank MiMo-V2.5-Pro DP-attention topology?
2. Should `SGLANG_MORI_NUM_MAX_DISPATCH_TOKENS_PER_RANK` and related heap settings scale differently when `--tp-size 16 --dp-size 2` is used?
3. Is there a known good MiMo-V2.5-Pro two-node DP-attention launch profile, distinct from the MiMo-V2-Flash guide?
4. Is `--page-size 64` required for this topology, or should the probe use the stable EP8 baseline's page-size=1 profile first?

## Evidence Index

- Status TSV: [`../data/tp16_dp2_probe_status_20260617.tsv`](../data/tp16_dp2_probe_status_20260617.tsv)
- Node 0 / Node 1 sanitized log excerpt: [`tp16_dp2_probe_errors_20260617.md`](tp16_dp2_probe_errors_20260617.md)
