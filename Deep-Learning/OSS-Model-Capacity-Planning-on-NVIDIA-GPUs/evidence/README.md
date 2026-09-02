# AIConfigurator run evidence

> Evidence class: **CPU-offline prediction**. No physical H100/H200 benchmark was run, and no production capacity is established.

This directory contains complete CLI stdout/stderr logs, machine-readable results, generated candidate configuration, and source-to-publication lineage for the worked examples. The README shows selected log excerpts; the files below are the complete records.

## Run index

| Run bundle | Question answered | Executed stages | Full logs | Data and generated output | Lineage |
|---|---|---|---|---|---|
| [`qwen3-32b-h200-trtllm-50rps`](runs/qwen3-32b-h200-trtllm-50rps/) | Can the supported Dense model meet the synthetic 50 req/s point, and which serving mode minimizes H200 count? | `support` PASS → initial `recommend` FAIL → dependency repair → unchanged `recommend` PASS | [`logs/`](runs/qwen3-32b-h200-trtllm-50rps/logs/) | [`results/`](runs/qwen3-32b-h200-trtllm-50rps/results/) | [`run-manifest.json`](runs/qwen3-32b-h200-trtllm-50rps/run-manifest.json) |
| [`qwen3-235b-h100-vllm-50rps`](runs/qwen3-235b-h100-vllm-50rps/) | What is the smallest worker that fits a large MoE model, and what does the planner itself cost to run? | 2-GPU boundary FAIL → 4-GPU worker PASS → request-rate sizing PASS → CPU footprint PASS | [`logs/`](runs/qwen3-235b-h100-vllm-50rps/logs/) | [`results/`](runs/qwen3-235b-h100-vllm-50rps/results/) | [`run-manifest.json`](runs/qwen3-235b-h100-vllm-50rps/run-manifest.json) |
| [`qwen3-235b-h100-vllm-real-workloads`](runs/qwen3-235b-h100-vllm-real-workloads/) | For fixed 16/32-GPU budgets, how much does workload shape change predicted capacity, and when does Disaggregated win? | coding-agent 16 GPU PASS → coding-agent 32 GPU PASS → chat 16 GPU PASS, all under `--strict-sla` | [`logs/`](runs/qwen3-235b-h100-vllm-real-workloads/logs/) | [`results/`](runs/qwen3-235b-h100-vllm-real-workloads/results/) | [`run-manifest.json`](runs/qwen3-235b-h100-vllm-real-workloads/run-manifest.json) |

## What each bundle preserves

- **Logs:** complete captured CLI stdout/stderr, warnings, traceback where applicable, and `EXIT_CODE`.
- **Top-N CSVs:** ranked candidate rows used for every GPU-count claim in the report.
- **Pareto CSVs:** the broader feasible frontier, not only the selected row.
- **Experiment configuration:** the search inputs and candidate ranges used by AIConfigurator.
- **Generated configuration:** the Top-1 candidate configuration emitted by the tool. It remains a deployment candidate until accepted by a version-aligned runtime.
- **Run manifest:** tool/environment identity, workload, exact command argv, stage status, source SHA-256, published SHA-256, and redaction counts.

## Log publication boundary

[`publish_run_evidence.py`](../tools/publish_run_evidence.py) and [`publish_real_scenario_evidence.py`](../tools/publish_real_scenario_evidence.py) copy only a fixed allowlist. They replace host identity and absolute local paths while preserving timestamps, numeric values, CLI messages, warnings, traceback, and exit codes. Each manifest records both the original source hash and the published hash for every file.

Validate the complete evidence set from the repository root:

```bash
python tools/validate_evidence.py
```

Expected terminal line:

```text
EVIDENCE_VALIDATION=PASS RUNS=3 PUBLIC_BOUNDARY=PASS
```

## 中文说明

这里保存的是三组 **CPU 离线预测**的完整证据，不是 H100/H200 实机 benchmark。主 README 只展示关键日志片段；本目录保留完整 stdout/stderr、失败 traceback、退出码、Top-N 与 Pareto CSV、实验配置、Top-1 候选配置，以及从原始文件到公开文件的 SHA-256 追溯关系。

三组证据分别回答不同问题：`qwen3-32b-h200-trtllm-50rps` 按请求率做采购规模估算；`qwen3-235b-h100-vllm-50rps` 确定大模型能装下的最小 worker，并测量规划器自身的 CPU 开销；`qwen3-235b-h100-vllm-real-workloads` 在固定 16/32 卡预算下对比长上下文 Coding Agent 与短上下文 Chat 两种工作负载场景，三次运行都启用 `--strict-sla`。