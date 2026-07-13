# AMD Tuned Fused-MoE Expanded Concurrency Bundle

This bundle reproduces all four AMD-provided serving steps once and expands the concurrency ranges using the repository's existing benchmark style. It uses the same two `Standard_ND96isr_MI300X_v5` nodes, the same MiMo-V2.5-Pro model, and the same Docker image as the earlier retest. The tested change is the model-specific aiter tuning at `d725746`; this is not a different VM SKU.

## Files

| File | Purpose |
|---|---|
| `launch_pd_prefill.sh`, `launch_pd_decode.sh`, `launch_pd_router.sh` | Start the TP=8 1P1D topology |
| `launch_dp2_node0.sh`, `launch_dp2_node1.sh`, `launch_dp2_router.sh` | Start two TP=8 prefill workers and the round-robin router |
| `benchmark_decode.sh` | Run the eight-point Decode concurrency sweep |
| `benchmark_1p_prefill.sh` | Run the twelve-point 1P1D Prefill sweep |
| `benchmark_dp2_prefill.sh` | Client-only convenience sweep; not sufficient for accepted evidence by itself |
| `benchmark_dp2_point.sh` | Run one DP=2 point between worker-count snapshots |
| `benchmark_common.sh` | Fail-closed client runner shared by all three sweeps |
| `validate_server_info.py` | Capture and validate direct worker context capacity |
| `validate_service_logs.py` | Reject context, watchdog, OOM, engine, and worker failures |
| `write_distribution.py` | Validate and write per-point DP=2 worker request deltas |
| `summarize_single_full.py` | Build deterministic JSON/Markdown with accepted and rejected points |
| `update_manifest.py` | Regenerate `SHA256SUMS.txt` for the public bundle |
| `mimo_v2_5_pro_b16_tuned_fmoe.csv` | Model-specific tuned fused-MoE configuration |

## Matrix

| Surface | Input / output | Concurrency | Requests per point |
|---|---|---|---:|
| 1P1D Decode | 8,192 / 1,024 | 8, 16, 32, 64, 96, 128, 192, 256 | 256 |
| 1P1D Prefill | 8,192 / 1; 65,536 / 1; 262,144 / 1 | 1, 2, 4, 8 | 16 |
| DP=2 Prefill | 8,192 / 1; 65,536 / 1; 262,144 / 1 | 1, 2, 4, 8, 16 | 32 |

This is one complete expanded matrix. It does not claim that all 35 points were repeated three times. Decode concurrency 16/32/64/128 also has a separate earlier fresh-service retest and can be compared as two runs.

The point guards are 600 seconds for 1P1D Prefill and 900 seconds for DP=2 Prefill. DP=2 256K/concurrency-1 runs 32 sequential requests at about 20.6 seconds each in this environment; a 600-second guard is too short even when the service is healthy.

The 1P1D Prefill workload intentionally uses output length 1. Most sustained GPU work therefore occurs on the Prefill node; the Decode node receives the transferred KV state and generates one token, so low sustained Decode utilization is expected. Confirm Decode participation from requests in both worker logs, not from an instantaneous GPU-utilization sample.

## Source Pin

```bash
git clone https://github.com/sammysun0711/aiter.git /sgl-workspace/aiter_0625
cd /sgl-workspace/aiter_0625
git checkout d725746a0f8c233d8e46e2771a7c8dbcd06e40d9
pip install -e . --no-deps
```

The tuned CSV SHA-256 is:

```text
2c87ff1fa062c73e1941962f8630a335ea1e39d2dbb5b0c2d4971bcd55880ea7
```

## 1. Start 1P1D Servers

On the prefill node:

```bash
LOG_DIR=/data/mimo-tuned-expanded/rep-1/onep/service \
  bash launch_pd_prefill.sh
```

On the decode node:

```bash
LOG_DIR=/data/mimo-tuned-expanded/rep-1/onep/service \
  bash launch_pd_decode.sh
```

Before launching the router, capture and validate each direct worker's capacity:

```bash
python3 validate_server_info.py \
  http://127.0.0.1:30000/server_info \
  --output /data/mimo-tuned-expanded/rep-1/onep/service/prefill_server_info.json
```

Run the equivalent command against port `30001` on the decode node. Both files must report `context_length=262151` and `max_req_input_len>=262145`.

## 2. Run 1P1D Decode and Prefill

On the prefill node:

```bash
PREFILL_IB_IP=<prefill-ib-ip> \
DECODE_IB_IP=<decode-ib-ip> \
LOG_DIR=/data/mimo-tuned-expanded/rep-1/onep/service \
  bash launch_pd_router.sh
```

`launch_pd_router.sh` uses `ROUTER_HEALTH_CHECK_ENDPOINT=/server_info` and a 30-second timeout by default. SGLang `/health` launches a synthetic generation probe that can fail during long Prefill requests; `/server_info` is non-generative. Health checks remain enabled, and exact request counts plus worker/router logs still fail closed.

In another shell on the prefill node:

```bash
export DATASET_PATH=/path/to/ShareGPT_V3_unfiltered_cleaned_split.json
LOG_DIR=/data/mimo-tuned-expanded/rep-1/decode bash benchmark_decode.sh
LOG_DIR=/data/mimo-tuned-expanded/rep-1/prefill bash benchmark_1p_prefill.sh
```

## 3. Start DP=2 Servers and Router

On node 0:

```bash
LOG_DIR=/data/mimo-tuned-expanded/rep-1/dp2/service \
  bash launch_dp2_node0.sh
```

On node 1:

```bash
LOG_DIR=/data/mimo-tuned-expanded/rep-1/dp2/service \
  bash launch_dp2_node1.sh
```

Validate `/server_info` directly on both workers before starting the router.

On node 0:

```bash
Node0_IP=<node0-ib-ip> \
Node1_IP=<node1-ib-ip> \
LOG_DIR=/data/mimo-tuned-expanded/rep-1/dp2/service \
  bash launch_dp2_router.sh
```

The DP=2 router uses explicit `round_robin`, `/server_info` health checks, and the same 30-second timeout. Two registered workers alone are not sufficient evidence that both processed benchmark requests.

## 4. Run DP=2 Prefill

For accepted evidence, run each point separately so worker counts bracket that point. On node 0 and node 1, capture the count before the point:

```bash
grep -c 'POST /generate' \
  /data/mimo-tuned-expanded/rep-1/dp2/service/node0_outer.log

grep -c 'POST /generate' \
  /data/mimo-tuned-expanded/rep-1/dp2/service/node1_outer.log
```

Run one point on node 0:

```bash
LOG_DIR=/data/mimo-tuned-expanded/rep-1/dp2 \
  bash benchmark_dp2_point.sh 8192 4
```

Capture both counts again, then write the point evidence using the four observed values:

```bash
python3 write_distribution.py \
  --node0-before 0 --node0-after 16 \
  --node1-before 0 --node1-after 17 \
  --output /data/mimo-tuned-expanded/rep-1/dp2/benchmark_8192_out1_con4.distribution.tsv
```

The numbers above illustrate a valid 16/17 split. Use the actual counts from the two logs. The deltas must both be positive and must sum to 33 (32 measured requests plus one warmup). Repeat for all 15 points. `benchmark_dp2_prefill.sh` is available as a client-only convenience sweep, but it cannot produce accepted evidence without point-level worker snapshots.

## Acceptance

Every accepted point requires:

- Benchmark exit code `0` and the exact expected successful-request count.
- The expected throughput metric in the client log.
- Point metadata showing `context_length=262151`.
- Zero client fatal markers and zero fatal markers in both worker logs and the router log.
- GPU memory-access faults, HSA memory-aperture violations, and fatal Python aborts are hard failures even if the client exits `0`.
- Both server logs showing `mimo_v2_5_pro_b16_tuned_fmoe.csv` loaded.
- For DP=2, positive request deltas on both workers.

Validate copied service logs with:

```bash
python3 validate_service_logs.py \
  prefill_outer.log decode_outer.log router_outer.log \
  --profile onep \
  --output onep_service_validation.json

python3 validate_service_logs.py \
  node0_outer.log node1_outer.log router_outer.log \
  --profile dp2 \
  --output dp2_service_validation.json
```

Client HTTP status and `Successful requests` alone are not acceptance evidence. SGLang can return an error payload with HTTP 200, and a watchdog dump rejects the affected point even when the client exits `0`.

## Parse Results

After collecting the node 0 and node 1 evidence trees:

```bash
python3 summarize_single_full.py /path/to/remote-node0 \
  --node1-root /path/to/remote-node1 \
  --prior-results /path/to/20260713-first-retest-results.json \
  --run-id <run-id> \
  --output /path/to/results
```

The parser requires exactly 35 measured points and computes the two-run delta for Decode concurrency 16/32/64/128. If a measured point is rejected by external service evidence, bind that point to one unique archived fatal log explicitly:

```bash
  --reject-point 'decode:8192:1024:256=prefill watchdog dump' \
  --rejection-evidence 'decode:8192:1024:256=/path/to/archived/prefill_outer.log'
```

The `--reject-point` and `--rejection-evidence` point sets must match exactly. Repeat `--rejection-evidence` with the same point when one failure affects multiple service logs, such as a worker crash followed by a router failure. Every evidence log must be a unique physical file, and one log cannot support multiple rejected points. The parser does not infer a rejected boundary from a historical run ID or hidden snapshot path. It writes final JSON/Markdown only after all point, service, distribution, and rejection-evidence gates pass.

If a fresh-service retry succeeds after an earlier runtime failure, retain that contrary evidence explicitly. Repeat the same incident ID to bind unique logs from multiple nodes:

```bash
  --observed-failure 'dp2-256k-c2-gpu-fault=/path/to/node0_outer.log' \
  --observed-failure 'dp2-256k-c2-gpu-fault=/path/to/node1_outer.log'
```

Every observed-failure log must contain a hard-fail marker and have a unique physical inode. The canonical JSON records portable paths and SHA-256 values; a successful retry does not erase the incident from the robustness verdict.