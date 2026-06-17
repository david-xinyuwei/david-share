# Two-Round Micro-Matrix Recovery Report

Generated: 2026-06-17T00:47:20Z

Status: STOPPED_OR_FAILED

This report is auto-generated from VM8 /data/bench_ep8_micro_2x/ while the recovery benchmark runs.

## Purpose

The first monolithic H200-aligned matrix completed 8K/64K cases but showed long-context instability at 256K. This recovery pass splits the benchmark into bounded cases and repeats every measurement point twice.

## Evidence Files

- Repo summary TSV: data/micro_matrix_2x_summary_20260617.tsv
- Repo raw log: logs/micro_matrix_2x_results_20260617.log
- Workspace pulled artifacts: G:\AI-Super-Agent\x小米H200\reports\mi300x-micro-2x-20260617\

## Current Summary

```tsv
case	rep	input_len	output_len	bs	num_prompts	timeout_s	exit_code	status	success	input_tps	output_tps	median_ttft_ms	median_tpot_ms
prefill_8k	1	8192	1	4	16	900	0	OK	16	14521.17	1.77	2451.46	0.00
prefill_64k	1	65536	1	4	16	1800	0	OK	16	11304.87	0.17	23175.39	0.00
```

## Current Process Snapshot

```text
 129002    08:32:24 python3 -u -m sglang.launch_server --model-path /data/models/MiMo-V2.5-Pro --tp-size 8 --ep-size 8 --moe-a2a-backend mori --host 0.0.0.0 --port 30000 --trust-remote-code --disable-radix-cache --disable-cuda-graph --mem-fraction-static 0.75 --context-length 786432 --max-running-requests 128 --chunked-prefill-size 16384 --attention-backend triton --disaggregation-mode prefill --disaggregation-transfer-backend mooncake --disaggregation-ib-device mlx5_ib0,mlx5_ib1,mlx5_ib2,mlx5_ib3,mlx5_ib4,mlx5_ib5,mlx5_ib6,mlx5_ib7 --speculative-algorithm EAGLE --speculative-num-steps 3 --speculative-eagle-topk 1 --speculative-num-draft-tokens 4 --enable-multi-layer-eagle
 133663    08:29:18 sglang::router
```

