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

Exit criteria: at least three warm runs per concurrency point, covering c1/c4/c8/c16/c32/c64/c128 when the endpoint supports it. Report both request throughput and audio-hours/GPU-hour.

Recommended benchmark shape:

| Sweep | Starting values | Output |
|---|---|---|
| Short clip smoke | 8-16s audio, c1-c32 | Latency and quick regression signal |
| Production chunk | 30s chunks, c1-c128 | Throughput and capacity basis |
| Stress boundary | c256 or until >5-10% failures | Failure mode and timeout policy |
| Stream A/B | Stream OFF vs ON at c16/c32 | Batch API vs UI TTFT decision |

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
| Expected volume | Technical GPU-hour estimate |
| SLA and compliance constraints | Production risk register |

Exit criteria: technical capacity, monitoring, rollback plan, and failure boundaries are explicit. Pricing and commercial assumptions are handled outside this repo.

Sizing worksheet columns:

| Column | Meaning |
|---|---|
| Region / data zone | Where audio can be processed |
| SKU | GPU family and instance shape |
| audio-hours/GPU-hour | Measured from the same benchmark script |
| Capacity risk | Available now, request needed, or uncertain |
| Production role | Primary, overflow, batch-only, or stress-only |

