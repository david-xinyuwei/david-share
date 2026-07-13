# 2026-07-13 Tuned Fused-MoE Retest Bundle

This directory contains the accepted launch, benchmark, configuration, and result-parser files for run `tuned_moe_retest_20260713T014113Z`.

## Files

| File | Purpose |
|---|---|
| `launch_pd_prefill.sh` | Start the TP=8 1P1D prefill server on port 30000 |
| `launch_pd_decode.sh` | Start the TP=8 1P1D decode server on port 30001 |
| `launch_pd_router.sh` | Start the PD router on port 40000; requires `PREFILL_IB_IP` and `DECODE_IB_IP` |
| `benchmark_decode.sh` | Run the 8K/1K decode matrix at concurrency 16/32/64/128 |
| `benchmark_1p_prefill.sh` | Run 8K/64K/256K 1P1D prefill at concurrency 4 |
| `launch_dp2_node0.sh` | Start DP=2 node 0 with the validated 262,149-token server allowance |
| `launch_dp2_node1.sh` | Start DP=2 node 1 with the validated 262,149-token server allowance |
| `launch_dp2_router.sh` | Start the DP router; requires `Node0_IP` and `Node1_IP` |
| `benchmark_dp2_prefill.sh` | Run 8K/64K/256K DP=2 prefill at concurrency 4/8 |
| `mimo_v2_5_pro_b16_tuned_fmoe.csv` | Model-specific tuned fused-MoE configuration |
| `mimo_v2_5_pro_b16_untuned_fmoe.csv` | Model-specific untuned reference configuration |
| `summarize_results.py` | Parse matrix summaries into deterministic JSON and Markdown |

## Required Source Pin

```bash
git clone https://github.com/sammysun0711/aiter.git /sgl-workspace/aiter_0625
cd /sgl-workspace/aiter_0625
git checkout d725746a0f8c233d8e46e2771a7c8dbcd06e40d9
pip install -e . --no-deps
```

The tuned CSV SHA-256 must be:

```text
2c87ff1fa062c73e1941962f8630a335ea1e39d2dbb5b0c2d4971bcd55880ea7
```

## DP=2 256K Guard

Do not reduce `--context-length 262149` in the DP=2 launch scripts when running `random_input_len=262144` and `random_output_len=1`. The standard server path adds four tokens during request construction. A 262,144-token server allowance returns an HTTP 200 error payload, which a client-only success counter can misclassify.

After a DP=2 run, validate both client and service evidence:

```bash
grep -H "Successful requests:" "$LOG_DIR"/benchmark_*.log
grep -H "Input token throughput" "$LOG_DIR"/benchmark_*.log
grep -c "longer than the model's context length" node0_outer.log node1_outer.log
```

The accepted run has six `Successful requests: 32` entries and zero context-overflow entries on both nodes.

## Parse Results

Place `decode-summary.txt`, `prefill-summary.txt`, and `dp2-summary.txt` in one directory, then run:

```bash
python3 summarize_results.py /path/to/summaries \
  --run-id tuned_moe_retest_20260713T014113Z
```

This writes `results.json` and `RESULTS.md` without external Python dependencies.