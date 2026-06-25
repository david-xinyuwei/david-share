# Azure ASR PoC Plan

This plan starts only after the customer provides a minimal evidence pack.

## Phase A0 - Runtime Smoke

| Input | Output |
|---|---|
| Exact checkpoint or public equivalent | Model-load result and short-sample transcript |
| Clean GPU VM | Environment JSON |
| Public or customer-approved short audio | Smoke result JSON |

Exit criteria: model loads, one short sample transcribes, scripts compile.

## Phase A1 - Quality Baseline

| Input | Output |
|---|---|
| Frozen de-identified audio set | WER/CER/hotword JSON |
| Human transcript | Quality table |
| Hotword list | Hotword recall |

Exit criteria: baseline quality numbers are reproducible and source-linked.

## Phase A2 - Serving Benchmark

| Input | Output |
|---|---|
| Current endpoint and Azure candidate endpoint | RTF/P50/P95/concurrency comparison |
| Same audio set and decoding params | Fairness table |
| Framework startup commands | Environment and reproducibility notes |

Exit criteria: at least three warm runs per concurrency point.

## Phase A3 - Training Diagnosis

| Input | Output |
|---|---|
| Training command/config/logs | Bottleneck map |
| Environment facts | GPU/data/runtime diagnosis |
| Failure examples | Recovery plan |

Exit criteria: failures are classified by data, runtime, memory, optimizer, checkpoint, or quality.

## Phase A4 - Production Sizing

| Input | Output |
|---|---|
| Target region and timeline | Quota/capacity check plan |
| Expected volume | GPU-hour estimate |
| SLA and compliance constraints | Production risk register |

Exit criteria: capacity, monitoring, and rollback plan are explicit.

