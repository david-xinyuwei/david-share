# OSS Model Capacity Planning on NVIDIA GPUs

[![AIConfigurator](https://img.shields.io/badge/AIConfigurator-0.11.0-76B900)](https://github.com/ai-dynamo/aiconfigurator/tree/v0.11.0)
[![Evidence](https://img.shields.io/badge/evidence-CPU--offline%20prediction-087A80)](evidence/)
[![GPU scope](https://img.shields.io/badge/GPU%20scope-H100%20SXM%20%7C%20H200%20SXM-76B900)](https://ai-dynamo.org/aiconfigurator/support-matrix/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](../../LICENSE)

> A reusable open-source workflow that turns a model, workload, service objectives, inference runtime, and NVIDIA platform into ranked deployment candidates, then calibrates those predictions with targeted GPU benchmarks.

> Author: 魏新宇 (Xinyu Wei)

[English](README.md) | [中文](README-CN.md)

[Official projects](#2-official-oss-foundation) · [Planning method](#3-capacity-planning-contract) · [How it is measured](#4-how-estimation-and-measurement-fit-together) · [Integration plan](#5-proposed-oss-integration-and-contribution-plan) · [Roadmap](#6-proposed-implementation-roadmap) · [Examples](#7-worked-examples) · [Evidence](#appendix-b-evidence-and-references)

---

## 1. Executive overview

Capacity planning for open-source and open-weight models is not a lookup from parameter count to GPU count. The answer changes with model architecture and quantization, workload shape, latency objectives, target GPU topology, inference backend, and serving mode.

The workflow starts with versioned model, workload, and platform contracts. It uses NVIDIA AIConfigurator to produce ranked deployment candidates, sends only the discriminating candidates to a target-GPU benchmark, and carries measured prediction error plus operational reserve into the capacity decision. AI Simulate is an optional experimental extension for trace-level system-policy questions; it is not required for fixed-point sizing.

The two Qwen cases in Section 7 demonstrate the workflow. They are examples, not the scope of the tool. Their fixed 50 req/s input is a synthetic capacity scenario, not a universal throughput target.

## 2. Official OSS foundation

### 2.1 Upstream projects

| Project | Official source | Role in capacity planning | Status used here |
|---|---|---|---|
| NVIDIA AIConfigurator | [GitHub repository](https://github.com/ai-dynamo/aiconfigurator) · [v0.11.0](https://github.com/ai-dynamo/aiconfigurator/tree/v0.11.0) · [CLI guide](https://github.com/ai-dynamo/aiconfigurator/blob/v0.11.0/docs/cli_user_guide.md) | Performance modeling, configuration search, ranking, and deployment-config generation | Primary sizing engine; version `0.11.0`, commit `614b9c8c8725332533616786e2eb049df48935f0` |
| NVIDIA Dynamo | [GitHub repository](https://github.com/ai-dynamo/dynamo) | Distributed inference orchestration and a deployment target for generated configurations | Integration target; no deployment executed in this study |
| NVIDIA AI Simulate | [Dynamo v1.4.2 source](https://github.com/ai-dynamo/dynamo/tree/v1.4.2/aisimulate) | Experimental trace replay and search over engine and Dynamo deployment settings | Future integration option; not executed in this study |
| NVIDIA AIPerf | [GitHub repository](https://github.com/ai-dynamo/aiperf) | Load generation and measured runtime validation | Proposed calibration path; not executed here |
| llm-d | [GitHub repository](https://github.com/llm-d/llm-d) | Kubernetes distributed inference serving stack and generated deployment target | Integration target; no deployment executed in this study |
| vLLM | [GitHub repository](https://github.com/vllm-project/vllm) | Open-source inference backend | Used as a performance-database target in one local example; no model server was launched |
| SGLang | [GitHub repository](https://github.com/sgl-project/sglang) | Open-source inference backend | Supported upstream integration target; not executed here |
| TensorRT-LLM | [GitHub repository](https://github.com/NVIDIA/TensorRT-LLM) | NVIDIA-optimized inference backend | Used as a performance-database target in one local example; no model server was launched |

AIConfigurator is Apache-2.0 software. Its built-in performance profiles are centered on NVIDIA GPU platforms and framework-specific implementations, so an open software path does not make the capacity model hardware-vendor neutral.

**Method reference:** [AIConfigurator: Lightning-Fast Configuration Optimization for Multi-Framework LLM Serving, arXiv:2601.06288v1](https://arxiv.org/abs/2601.06288v1) defines the method, fidelity evaluation, search-efficiency evidence, and design boundaries. It is a method source, not an integration component.

### 2.2 Canonical end-to-end workflow

This is the single workflow used throughout the report:

| Stage | Owner | Input | Output and evidence |
|---|---|---|---|
| 1. Define | OSS integration layer | Pinned model, workload buckets, SLOs, NVIDIA GPU topology, backend version | Immutable model/workload/platform contracts |
| 2. Predict | AIConfigurator | Contracts plus supported performance database | Ranked Top-N configurations, predicted metrics, Pareto data, generated candidates |
| 3. Deploy | NVIDIA Dynamo or llm-d | Selected generated candidate with runtime-version alignment | Running candidate service and deployment identity |
| 4. Measure | AIPerf on target GPUs | Frozen request contract and candidate endpoint | Actual memory, latency, throughput, goodput, errors, and telemetry |
| 5. Calibrate | OSS integration layer | Predicted and measured records for the same tuple | Prediction-error ledger, operational reserve, and revised capacity |
| 6. Extend when needed | AI Simulate / Dynamo Replay | Sanitized production trace and dynamic-policy search space | Experimental router, planner, or policy candidates requiring independent benchmark validation |

Stages 1–2 are represented by the local examples. Stages 3–5 are proposed integration work and require target GPUs. Stage 6 is upstream-dependent and experimental.

### 2.3 What AIConfigurator contributes

Given a model, NVIDIA system, inference backend, workload descriptor, and latency constraints, AIConfigurator can:

- determine whether candidate topologies fit in GPU memory;
- search Tensor, Pipeline, Data, Expert, and MoE Tensor Parallelism where applicable;
- compare Static, Aggregated, and Disaggregated serving models;
- estimate TTFT, TPOT, request latency, memory, and throughput;
- rank Pareto-efficient candidates under the specified constraints;
- calculate replicas and total GPUs for a request-rate or concurrency target;
- generate candidate launch and deployment artifacts for supported runtimes and platforms.

It does not execute the model during ordinary configuration search, optimize kernels, operate the cluster, discover the production workload automatically, or replace a physical benchmark.

## 3. Capacity planning contract

The capacity question must be expressed as four input groups and one decision objective.

![Capacity-planning problem definition](images/configuration-problem.png)

**Figure 1. Original explanatory diagram.** Model, workload, service objective, backend, and hardware are joint inputs to configuration search. Source basis: [AIConfigurator CLI guide](https://github.com/ai-dynamo/aiconfigurator/blob/v0.11.0/docs/cli_user_guide.md) and [paper Section 4](https://arxiv.org/html/2601.06288v1). Image SHA-256: `42e48e0571826eb2f5f8457fe0d84e5b28df05f4da1acf2b2b0ab2616cdf868b`.

### 3.1 Model contract

| Field | Required detail |
|---|---|
| Model identity | Exact Hugging Face or local model ID plus revision |
| Architecture | Dense or MoE, layer count, hidden dimensions, attention and expert structure |
| Precision | BF16, FP8, FP4, INT8, or another exact quantization configuration |
| Context behavior | Native context, RoPE/YaRN settings, multimodal encoder inputs, MTP depth if used |

### 3.2 Workload contract

| Field | Required detail |
|---|---|
| Request shape | ISL, OSL, image shape/count when applicable, and prefix-cache eligibility |
| Arrival demand | Request-rate curve or concurrency, peak duration, and burst behavior |
| User behavior | Thinking/non-thinking mix, chat template, sampling, and output-token accounting |
| Service objectives | TTFT, TPOT, end-to-end latency, goodput, and error-rate targets |

A production analysis should use representative buckets such as normal traffic, peak traffic, and long-context tail traffic. A single average ISL/OSL pair is an example point, not a production distribution.

### 3.3 Platform contract

| Field | Required detail |
|---|---|
| GPU | Exact NVIDIA system name and memory capacity |
| Node topology | GPUs per node, NVLink/NVSwitch domain, and inter-node fabric |
| Backend | TensorRT-LLM, vLLM, or SGLang plus exact version |
| Deployment target | NVIDIA Dynamo, llm-d, bare metal, or another supported target |
| Operational reserve | Replica loss, rolling upgrade, startup, traffic burst, and tail-latency allowance |

### 3.4 Search and output

The search space can include serving mode, TP/PP/DP/EP/ETP, worker count, replica count, batch size, KV-cache allocation, chunked prefill, and supported runtime flags. The output is a ranked candidate set with predicted metrics and generated artifacts, not one context-free GPU number.

```text
capacity input  = model contract + workload contract + platform contract
candidate       = serving mode + parallelism + workers + batch/runtime settings
capacity output = ranked candidates + predicted metrics + generated artifacts
```

## 4. How estimation and measurement fit together

### 4.1 GPU work happens when the performance database is built

AIConfigurator's upstream data-collection process profiles operations such as GEMM, attention, MoE, AllReduce, AllGather, AllToAll, and point-to-point communication on target GPU and backend combinations. The resulting performance data is packaged for later search.

### 4.2 Ordinary configuration search runs on CPU

For a supported model/system/backend combination, the user-side search reads model metadata, queries the packaged performance data, interpolates supported shapes, composes iteration and serving behavior, filters infeasible candidates, and ranks the remainder. Model weights are not loaded during this path.

![Official AIConfigurator workflow](images/aic-workflow-official.png)

**Figure 2. Official AIConfigurator workflow, Figure 2 in arXiv:2601.06288v1.** Inspect the progression from PerfDatabase and TaskRunner through InferenceSession and Pareto Analyzer to Generator. [Public source](https://arxiv.org/html/2601.06288v1/AIC_assets/AIC-Workflow.png). Image SHA-256: `ee1db977c816218ca0cb6b8e3eff6237c1dd55051d507f0e5579d5b08012bc0f`.

### 4.3 Physical benchmarks calibrate the prediction

The generated candidate must still be deployed on the target runtime and hardware. AIPerf or an equivalent load generator measures actual memory, TTFT, TPOT, request latency, throughput, goodput, and error rate. The difference between predicted and measured values is retained by model, workload bucket, backend version, and GPU topology.

| Evidence layer | Uses GPUs? | What it proves |
|---|:---:|---|
| Upstream performance-data collection | Yes | Operation-level or forward-pass measurements for a declared system/backend/version |
| AIConfigurator search | No GPU required | Predicted candidate ranking for the supplied contracts |
| Generated deployment artifacts | No GPU required | Candidate configuration syntax for a selected target version |
| Target-runtime benchmark | Yes | Observed behavior for one exact model, workload, runtime, and hardware tuple |
| Production calibration | Yes | Capacity with measured error and operational reserve |

## 5. Proposed OSS integration and contribution plan

### 5.1 Objective

The proposed OSS integration should turn AIConfigurator from an expert-operated CLI into a repeatable capacity-planning workflow without replacing the upstream product. Its objective is to make every recommendation traceable from input contracts to prediction, generated configuration, target benchmark, and calibration.

The committed evidence captures official AIConfigurator CLI results for two OSS model examples. This repository does **not** contain a standalone adapter, upstream pull request, generic schema, or benchmark-calibration service. The items below are a proposed implementation plan.

### 5.2 Integration architecture

```mermaid
flowchart LR
    M[OSS model contract] --> P[Capacity-plan runner]
    W[Workload buckets and SLOs] --> P
    H[NVIDIA GPU and backend matrix] --> P
    P --> A[Official AIConfigurator CLI]
    A --> R[Ranked Top-N and generated configs]
    R --> D[Dynamo or llm-d candidate deployment]
    D --> B[AIPerf target benchmark]
    B --> C[Prediction-error and reserve ledger]
    C --> P
    T[Production trace] -. future .-> S[AI Simulate and Dynamo Replay]
    S -. policy candidates .-> R
```

The integration layer owns input normalization, run identity, evidence packaging, calibration, and policy around acceptable prediction error. AIConfigurator remains the configuration-search authority; Dynamo/llm-d own deployment; AIPerf owns measured load generation; AI Simulate owns its experimental trace-search path.

### 5.3 Proposed repository contracts

| Proposed surface | Contract | Status |
|---|---|---|
| `configs/models/` | Model ID, revision, architecture, precision, and context settings | Proposed |
| `configs/workloads/` | Named normal/peak/tail buckets with ISL/OSL, load, cache, and SLO fields | Proposed |
| `configs/platforms/` | NVIDIA GPU, node topology, backend/database version, and deployment target | Proposed |
| `runs/<run-id>/inputs/` | Immutable copies of all contracts plus source hashes | Proposed |
| `runs/<run-id>/prediction/` | Official CLI argv, logs, Top-N CSVs, Pareto output, and generated configs | Example artifacts captured locally; generic contract proposed |
| `runs/<run-id>/benchmark/` | Runtime/image identity, AIPerf command, raw measurements, and telemetry | Proposed; GPU execution not yet performed here |
| `runs/<run-id>/calibration.json` | Prediction/measurement delta and approved reserve by metric | Proposed |
| `adapters/` | Thin, versioned invocation adapters for official CLI and deployment targets | Proposed; must not reimplement AIConfigurator logic |

## 6. Proposed implementation roadmap

| Phase | Deliverable | Completion signal | Current status |
|---|---|---|---|
| 0. Reference evidence | Preserve official CLI commands, logs, Top-N CSVs, generated configs, and hashes | At least one Dense and one MoE/open-weight example can be audited locally | Example Top-N evidence committed; reusable run manifest not implemented |
| 1. Contract layer | JSON Schema or YAML contracts for model, workload, platform, and objective | Invalid or incomplete capacity questions fail before search | Proposed |
| 2. Generic runner | Invoke upstream `support`, `default`, `recommend`, and selected `exp` workflows without changing their semantics | One command produces an isolated run directory and evidence manifest | Proposed |
| 3. Matrix and comparison | Sweep model x NVIDIA GPU x backend x workload bucket and retain Top-N | Results remain separated by exact version and evidence class | Proposed |
| 4. Benchmark calibration | Deploy selected candidates and run AIPerf near predicted operating points | Predicted-versus-observed deltas and reserve are machine-readable | Proposed; requires target GPUs |
| 5. Community contribution | Add reproducible model/backend coverage through upstream issues, data collection, or pull requests | Accepted upstream artifact or publicly reviewable contribution | Proposed; no PR exists yet |
| 6. Trace-level extension | Feed sanitized traces into AI Simulate/Dynamo Replay for router, planner, and policy search | Trace experiment is version-pinned and independently benchmarked | Upstream-dependent and experimental |

The first public milestone should stop after Phase 2: publish the schemas, two example contracts, and a thin runner that invokes the official CLI without reimplementing search logic. Matrix automation, GPU calibration, upstream contributions, and AI Simulate remain later milestones with separate evidence.

![AIConfigurator and AI Simulate boundary](images/aic-aisimulate-boundary.png)

**Figure 3. Original boundary diagram based on public AIConfigurator v0.11.0 and Dynamo v1.4.2 sources.** AIConfigurator can run independently for fixed workload descriptors. AI Simulate/Spica extends the search with Dynamo Replay and remains experimental. [AI Simulate source](https://github.com/ai-dynamo/dynamo/tree/v1.4.2/aisimulate). Image SHA-256: `0b7c56f3dc0b18504a09c20864ae371b6e097b9057497e10cfbcbea301fbb3ab`.

## 7. Worked examples

The examples below prove that the same planning method can represent different model sizes, architectures, NVIDIA GPUs, and inference backends. They do not define a fixed service target for the general workflow.

| Example | Model | Target platform | Backend database | Synthetic workload | Main predicted result |
|---|---|---|---|---|---|
| Dense-model canary | `Qwen/Qwen3-32B-FP8` | H200 SXM | TensorRT-LLM | ISL 4,000; OSL 1,000; TTFT <=2,000 ms; TPOT <=30 ms; 50 req/s | 32 H200 Aggregated versus 34 H200 Disaggregated |
| MoE large-model case | `Qwen/Qwen3-235B-A22B-FP8` | H100 SXM | vLLM `0.24.0` | ISL 4,000; OSL 1,000; TTFT <=2,000 ms; TPOT <=30 ms; 50 req/s | Four-GPU `TP4/ETP4` worker; 428-H100 Aggregated example capacity |

### 7.1 Qwen3-32B-FP8 on H200 SXM

The upstream `support` and `recommend` paths completed on CPU. Under the example workload, the top Aggregated result uses 32 one-GPU replicas, while the top Disaggregated result uses 17 replicas with one prefill and one decode GPU each, for 34 GPUs total.

![Qwen3-32B H200 example](images/qwen3-32b-h200-canary.png)

**Figure 4. Local CPU-offline prediction, not an H200 benchmark.** AIConfigurator v0.11.0, Qwen3-32B-FP8, H200 SXM, TensorRT-LLM, synthetic 50 req/s workload. [Aggregated CSV](evidence/qwen3-32b-h200-agg-topn.csv) · [Disaggregated CSV](evidence/qwen3-32b-h200-disagg-topn.csv). Image SHA-256: `b290bbd126594ca3ac923591b567f6b4cd5e838de6c73ef512405aa3caa08690`.

### 7.2 Qwen3-235B-A22B-FP8 on H100 SXM

The same workflow was applied to a 235B-total / 22B-active MoE model with 128 experts and 8 activated experts. A two-GPU budget produced no feasible candidate in the search. The smallest modeled worker uses four H100 SXM GPUs with `TP4/PP1/DP1/ETP4/EP1`. At the synthetic 50 req/s point, the top Aggregated result uses 107 four-GPU replicas, or 428 GPUs.

```text
107 replicas x 4 H100 SXM GPUs = 428 H100 SXM GPUs
```

![Qwen3-235B H100 example](images/qwen3-235b-h100-pareto.png)

**Figure 5. Local CPU-offline prediction, not an H100 benchmark.** AIConfigurator v0.11.0, Qwen3-235B-A22B-FP8, H100 SXM, vLLM 0.24.0, synthetic 50 req/s workload. The 428-GPU value comes from the ranked CSV, not from reading this plot. [Aggregated CSV](evidence/qwen3-235b-h100-agg-topn.csv) · [Disaggregated CSV](evidence/qwen3-235b-h100-disagg-topn.csv). Image SHA-256: `2f0aef7b052857e3084b518a29a159bf9ab6a1e47e380a3c59d3126756a8c352`.

The run logs also record that vLLM `0.24.0` had no FP8 `context_attention` performance data for H100 SXM, so AIConfigurator fell back to BF16 FMHA data. The 235B/H100 numbers are version-specific predictions with this database-fallback boundary.

The 428 result is not the capacity requirement for Qwen3-235B in general. It belongs to one model revision family, target system, backend database, workload point, and SLA. A different output-length distribution, request rate, cache profile, backend, or GPU changes the result.

## 8. Boundaries and risks

| Boundary | Implication |
|---|---|
| Support matrix coverage is version-specific | Unsupported combinations require a different backend/system, explicit research-mode downgrade, or new measured data |
| `SILICON` refers to measured database inputs | End-to-end TTFT, TPOT, memory, and throughput remain modeled outputs until benchmarked |
| vLLM and SGLang alignment is still called out in upstream known issues | Production use requires target-version measurement |
| Search, generator, and runtime versions can differ | Generated YAML is a candidate until the actual runtime accepts and serves it |
| One workload point is not a traffic distribution | Capacity must be recomputed for normal, peak, and tail buckets |
| Prediction error is not operational reserve | Tail latency, bursts, failures, startup, and upgrades require separate allowance |
| AI Simulate is experimental | It provides no SLA, accuracy, or global-optimality guarantee |
| The committed evidence contains CPU-offline predictions only | No committed result proves physical H100/H200 performance or production capacity |

## Appendix A. Generic upstream entry points

```bash
aiconfigurator cli support \
  --model-path <model-id-or-path> \
  --system <nvidia-system> \
  --backend <trtllm-vllm-or-sglang>

aiconfigurator cli recommend \
  --model-path <model-id-or-path> \
  --system <nvidia-system> \
  --backend <trtllm-vllm-or-sglang> \
  --target-concurrency <concurrent-requests> \
  --isl <input-tokens> \
  --osl <output-tokens> \
  --ttft <milliseconds> \
  --tpot <milliseconds> \
  --database-mode SILICON \
  --strict-sla \
  --save-dir <isolated-run-directory>
```

`--target-request-rate <req/s>` can replace `--target-concurrency`; the two load targets are mutually exclusive. These values come from the workload contract, not from a hard-coded project default.

### Rebuild the original figures

The figure generator requires Python 3.11, Pillow 12.3.0, and the Segoe UI fonts included with Windows. It regenerates Figures 1, 3, and 4 from the committed source and CSV evidence.

```powershell
python -m pip install -r requirements.txt
python tools/make_report_figures.py
```

## Appendix B. Evidence and references

### Committed evidence

- [Qwen3-32B/H200 Aggregated Top-N CSV](evidence/qwen3-32b-h200-agg-topn.csv)
- [Qwen3-32B/H200 Disaggregated Top-N CSV](evidence/qwen3-32b-h200-disagg-topn.csv)
- [Qwen3-235B/H100 Aggregated Top-N CSV](evidence/qwen3-235b-h100-agg-topn.csv)
- [Qwen3-235B/H100 Disaggregated Top-N CSV](evidence/qwen3-235b-h100-disagg-topn.csv)
- [Original figure generator](tools/make_report_figures.py)

### Public references

- [AIConfigurator repository](https://github.com/ai-dynamo/aiconfigurator)
- [AIConfigurator v0.11.0 CLI guide](https://github.com/ai-dynamo/aiconfigurator/blob/v0.11.0/docs/cli_user_guide.md)
- [AIConfigurator paper](https://arxiv.org/abs/2601.06288v1)
- [AIConfigurator support matrix](https://ai-dynamo.org/aiconfigurator/support-matrix/)
- [NVIDIA Dynamo](https://github.com/ai-dynamo/dynamo)
- [llm-d](https://github.com/llm-d/llm-d)
- [AI Simulate v1.4.2](https://github.com/ai-dynamo/dynamo/tree/v1.4.2/aisimulate)
- [NVIDIA AIPerf](https://github.com/ai-dynamo/aiperf)