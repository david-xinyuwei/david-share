# AMD Latest MiMo-V2.5-Pro MI300X Reproduction

This is the only supported reproduction bundle in the repository. Use these files from a pinned checkout of the current repository; the immutable runtime image supplies the tested software stack but may contain an older embedded copy of this bundle.

## Topologies

| Topology | Launch scripts | Benchmark |
|---|---|---|
| 1P1D, TP=8 + TP=8 | `launch_pd_prefill.sh`, `launch_pd_decode.sh`, `launch_pd_router.sh` | `benchmark_1p_prefill.sh`, optional `benchmark_1p_prefill_long_isl_selected.sh`, `benchmark_decode.sh`, optional `benchmark_decode_long_context.sh` |
| Two-node DP=2 Prefill, TP=8 per worker | `launch_dp2_node0.sh`, `launch_dp2_node1.sh`, `launch_dp2_router.sh` | `benchmark_dp2_prefill.sh` |
| Single-node TP=8 exact Decode | `launch_single_node_decode.sh` | `benchmark_decode_fixed_batch.sh`; optional `benchmark_decode_fixed_batch_bs4.sh` for 128K/192K |

Both worker launch paths use context length 262151 and the model-specific tuned fused-MoE CSV. The 256K-input Prefill clients use `--tokenize-prompt` so each request sends exactly 262,144 token IDs.

`benchmark_decode.sh` reproduces the default 8K-input / 1K-output Decode comparison. `benchmark_decode_long_context.sh` runs a separately validated requested-64K concurrency sweep and a requested-255K-input / 1K-output capability point using random-text framing. The latter is a nominal 256K **total-sequence** point; it is not a 256K-input or exact-token claim, because 256K input plus 1K output exceeds context length 262151.

For these long-context runs, SGLang's `Output token throughput` is an **end-to-end** metric: total generated output tokens divided by the full benchmark duration, including Prefill/TTFT. It is not pure Decode-server capacity. Always report it together with Input token throughput, TPOT, and TTFT.

## Exact 64K/1K Fixed-Batch Decode

The 64K headline is a **fixed-acceptance performance benchmark** using `SGLANG_SIMULATE_ACC_LEN=3` with `match-expected`. It uses the Decode scheduler's steady-state `gen throughput`, not the client E2E output rate. It does not validate natural MTP acceptance or output quality. Run two independent repetitions, restarting the service before each one:

```bash
export LOG_DIR=/data/mimo-fixedbatch/service
bash launch_single_node_decode.sh

# After /health is ready and the bpreshuffle marker appears in the service log:
export SERVICE_LOG=/data/mimo-fixedbatch/service/decode_outer.log
export REP=1  # use REP=2 after stopping and starting a fresh service
bash benchmark_decode_fixed_batch.sh
```

The benchmark script fails closed unless all 16 requests succeed with exactly 1,048,576 total input tokens, 16,384 server-accounted generated tokens, and 4,112 retokenized generated-text tokens. Retokenized means `tokenizer.encode(generated_text)` length; it is not accepted draft-token count. The script also captures the scheduler-log window and rejects missing accept-length evidence, fatal markers, or a service log without `module_gemm_a8w8_blockscale_bpreshuffle`/`BpreShuffle`.

For each repetition, apply the documented transition guard: exclude exactly the first full-batch sample if and only if its throughput is below 50% of the median of all subsequent full-batch samples. Report the arithmetic mean of the two fresh-service steady-state means and the run-to-run delta.

The published sanitized windows are under `data/evidence/exact64-fixed-acceptance/`. Run `python3 scripts/analyze_exact64_evidence.py` to verify their SHA-256 manifest and rebuild the 933.75 tok/s optimized mean, 743.12 tok/s baseline, and 25.7% bundle uplift.

## Controlled 128K/192K Selected Points

The selected Prefill points use 1P1D PD, client concurrency 4, 16 prompts, and OSL 1:

```bash
export LOG_DIR=/data/mimo-amd-latest/onep/prefill-long-isl-selected
export DATASET_PATH=/data/datasets/ShareGPT_V3_unfiltered_cleaned_split.json
bash benchmark_1p_prefill_long_isl_selected.sh
```

The selected Decode points use the single-node service, actual batch 4, four prompts, OSL 1K, and the same fixed-acceptance configuration as the exact64 performance method:

```bash
export SERVICE_LOG=/data/mimo-fixedbatch/service/decode_outer.log
export DATASET_PATH=/data/datasets/ShareGPT_V3_unfiltered_cleaned_split.json
export INPUT_TOKENS=131072  # use 196608 for the second point
bash benchmark_decode_fixed_batch_bs4.sh
```

Each point has one accepted measurement run. The Decode headline is transition-guarded steady full-BS4 scheduler generation throughput; the Prefill headline is aggregate input tok/s. Do not divide or combine these metrics. The sanitized evidence is under `data/evidence/controlled-isl-128k-192k/`; run `python3 scripts/analyze_controlled_isl_evidence.py` to rebuild all four points and their 128K-to-192K deltas.

## Required Environment

```bash
export BUNDLE_DIR=/data/david-share/Deep-Learning/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/amd-latest
cd "$BUNDLE_DIR"
sha256sum -c SHA256SUMS.txt
export MODEL=/data/models/MiMo-V2.5-Pro
export DATASET_PATH=/data/datasets/ShareGPT_V3_unfiltered_cleaned_split.json
```

For 1P1D, also set the two InfiniBand addresses before starting the router:

```bash
export PREFILL_IB_IP=<prefill-node-ib-ip>
export DECODE_IB_IP=<decode-node-ib-ip>

# Prefill node:
SERVER_HOST="$PREFILL_IB_IP" bash launch_pd_prefill.sh

# Decode node:
SERVER_HOST="$DECODE_IB_IP" bash launch_pd_decode.sh

# Prefill/router node, after both workers are ready:
ROUTER_BIND_HOST="$PREFILL_IB_IP" bash launch_pd_router.sh

# Benchmark client on the router node:
export ROUTER_HOST="$PREFILL_IB_IP"
```

## Capacity Gate

Capture `/server_info` directly from every worker before measurement:

```bash
python3 validate_server_info.py "http://${PREFILL_IB_IP}:30000/server_info" \
  --output /data/mimo-amd-latest/prefill-server-info.json
```

Require `context_length=262151` and `max_req_input_len>=262145` on every worker.

## Validation

After each topology completes, run `validate_service_logs.py` over its two worker logs and router log. For DP=2, also use `write_distribution.py` to preserve the two-worker request distribution. The 256K result is accepted only when every request has a retokenized output and service logs contain no context or fatal markers.