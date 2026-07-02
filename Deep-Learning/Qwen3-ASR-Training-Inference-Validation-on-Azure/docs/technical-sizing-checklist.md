# Technical Sizing Checklist

Use this checklist when turning ASR benchmark results into a technical GPU comparison. It is designed for customer-owned ASR services where this repo is responsible for runtime behavior, throughput, concurrency, and long-audio robustness. Commercial terms are out of scope for this artifact.

## 1. Inputs to Freeze

| Input | Required value |
|---|---|
| Audio set | Same files, same duration buckets, same sample rate, same language mix |
| Chunking policy | VAD, target chunk seconds, overlap seconds, stitching rules |
| Endpoint contract | Request route, multipart field name, headers, output parser, stream mode |
| Model/runtime | Checkpoint, precision, vLLM/SGLang/TRT version, CUDA/cuDNN/PyTorch versions |
| Region/data zone | Where the technical benchmark can run |
| GPU shape | GPU SKU, visible HBM, CPU/memory shape, runtime container |

Do not compare runtimes or GPU shapes until these inputs are frozen.

## 2. Recommended First Sweep

| Sweep | Values | Decision produced |
|---|---|---|
| Short smoke | 8-16s audio at c1/c4/c8/c16/c32 | Endpoint health and quick latency regression |
| Production chunks | 30s audio chunks at c1/c4/c8/c16/c32/c64/c128 | Main throughput and capacity basis |
| Stress boundary | c256 or until failures exceed 5-10% | Backpressure and timeout policy |
| Stream A/B | stream OFF vs ON at c16/c32 | Batch API vs UI TTFT policy |
| Long stitched sample | One meeting-length sample after VAD/chunk/stitching | Product-level correctness check |

## 3. Technical Throughput Formula

```text
audio_hours_per_gpu_hour = total_audio_seconds_processed / wall_seconds
```

Notes:

- `req/s` is not enough because one request may contain 2 seconds, 30 seconds, or a whole chunked meeting.
- Report `audio_hours_per_gpu_hour` as the handoff metric for downstream capacity and commercial analysis.
- Keep non-technical commercial terms outside this repo.

## 4. Interpreting the H100 Results in This Repo

| Result | How to use it |
|---|---|
| c32 on 8-16s FLEURS audio: P50 395ms, throughput 74.9 req/s, 100% success | Good first H100 interactive/balanced serving candidate |
| c128: 100% success, P50 4.3s | Batch-only upper bound, not an interactive default |
| c256: 89.6% success | Stress/failure boundary, not production sizing |
| 180s direct input collapsed to 16 output chars | Do not use whole meeting audio as a single request |
| Stream ON added about 8% total latency | Use stream for UI perceived latency, not for batch throughput optimization |

## 5. Output Table Template

| Region/data zone | GPU shape | Runtime | Chunk | Concurrency | P50/P95 | RTF | req/s | audio-hours/GPU-hour | success rate | GPU utilization | Role |
|---|---|---|---|---:|---|---|---:|---:|---:|---|---|
| `<region>` | `<sku>` | `<vLLM version>` | `30s + 1s overlap` | 32 | `<p50>/<p95>` | `<rtf>` | `<req/s>` | `<measured>` | `<%>` | `<SM% / HBM%>` | Primary / overflow / batch / stress |

## 6. Evidence Block

```text
Environment: <GPU SKU>, <region/data zone>, <driver>, <CUDA>, <framework versions>
Model: <checkpoint>, <precision>, <backend>
Audio set: <N files>, <total seconds>, <duration buckets>, <ground truth status>
Chunking: <VAD>, <target seconds>, <overlap>, <stitching>
Command: <exact command>
Result files: <paths>
Sizing: <audio-hours/GPU-hour>, <concurrency knee point>, <failure boundary>
Limitations: <what this run does not prove>
```