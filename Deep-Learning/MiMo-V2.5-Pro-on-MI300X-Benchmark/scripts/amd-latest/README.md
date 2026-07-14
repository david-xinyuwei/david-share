# AMD Latest MiMo-V2.5-Pro MI300X Reproduction

This is the only supported reproduction bundle in the repository. It runs the final customer-facing workloads shown in the top-level README.

## Topologies

| Topology | Launch scripts | Benchmark |
|---|---|---|
| 1P1D, TP=8 + TP=8 | `launch_pd_prefill.sh`, `launch_pd_decode.sh`, `launch_pd_router.sh` | `benchmark_1p_prefill.sh`, `benchmark_decode.sh` |
| Two-node DP=2 Prefill, TP=8 per worker | `launch_dp2_node0.sh`, `launch_dp2_node1.sh`, `launch_dp2_router.sh` | `benchmark_dp2_prefill.sh` |

Both worker launch paths use context length 262151 and the model-specific tuned fused-MoE CSV. The 256K clients use `--tokenize-prompt` so each request sends exactly 262,144 token IDs.

## Required Environment

```bash
export MODEL=/data/models/MiMo-V2.5-Pro
export DATASET_PATH=/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json
```

For 1P1D, also set the two InfiniBand addresses before starting the router:

```bash
export PREFILL_IB_IP=<prefill-node-ib-ip>
export DECODE_IB_IP=<decode-node-ib-ip>
```

## Capacity Gate

Capture `/server_info` directly from every worker before measurement:

```bash
python3 validate_server_info.py http://127.0.0.1:30000/server_info \
  --output /data/mimo-amd-latest/prefill-server-info.json
```

Require `context_length=262151` and `max_req_input_len>=262145` on every worker.

## Validation

After each topology completes, run `validate_service_logs.py` over its two worker logs and router log. For DP=2, also use `write_distribution.py` to preserve the two-worker request distribution. The 256K result is accepted only when every request has a retokenized output and service logs contain no context or fatal markers.