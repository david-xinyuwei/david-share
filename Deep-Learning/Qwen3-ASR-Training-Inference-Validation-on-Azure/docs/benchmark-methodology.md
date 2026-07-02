# ASR Benchmark Methodology

This document defines how to run a fair ASR benchmark once customer-owned data and endpoints are available.

## 1. Benchmark Variables

Only change one variable per comparison.

| Variable | Must stay fixed |
|---|---|
| Audio input | Same files, duration, sample rate, channel count, and language mix |
| Ground truth | Same human transcript and hotword list |
| Model | Same checkpoint unless the comparison is explicitly a model comparison |
| Decoding | Same language hints, max tokens, timestamp mode, sampling/beam params |
| Pipeline | Same VAD, chunking, overlap, stitching, diarization, post-processing |
| Hardware | Same GPU SKU, driver, CUDA, framework version |
| Request load | Same concurrency, request order, timeout, warm-up policy |

## 2. Minimum Runs

| Benchmark | Minimum |
|---|---|
| Runtime smoke | 1 run is enough to prove load path |
| Quality metric | One frozen eval set; repeat after any model/pipeline change |
| Serving benchmark | 3 warm runs per concurrency point; discard first cold run |
| Long-audio pipeline | At least one short, one medium, and one meeting-length sample |
| Production sizing | Repeated load plus failure-path tests |

## 3. Required Output Columns

| Category | Required fields |
|---|---|
| Quality | WER, CER, hotword recall, sample count, language mix |
| Serving | RTF P50/P95, latency P50/P95, success rate, timeout count, audio-hours/GPU-hour |
| Environment | GPU SKU, driver, CUDA, PyTorch, transformers, vLLM/SGLang/TRT versions |
| Data | audio file ID, duration, language, speaker count, codec/sample rate |
| Technical capacity | Region/data zone, GPU SKU, runtime, concurrency, audio-hours/GPU-hour, failure boundary |

## 4. Interpretation Rules

- Do not report WER/CER without ground truth.
- Do not report framework superiority unless input, model, decoding, pipeline, and hardware are controlled.
- Do not treat mock endpoint speed as ASR speed.
- Do not average short and long audio without showing duration buckets.
- Do not turn throughput into business claims until utilization and serving topology are measured.
- Keep non-technical commercial terms outside this benchmark artifact.

## 5. Technical Sizing Protocol

Run serving tests in two passes:

1. **Latency pass**: report P50/P95 and success rate per concurrency level.
2. **Throughput pass**: report audio-hours processed per GPU-hour.

Recommended first sweep:

| Dimension | Starting values | Notes |
|---|---|---|
| Audio duration buckets | 8-16s, 30s chunks, one meeting-length stitched sample | Do not infer meeting behavior from 2-3s demo clips. |
| Concurrency | 1, 4, 8, 16, 32, 64, 128, optional 256 stress | Pick a knee point, not the largest number that starts. |
| Stream mode | OFF for batch, ON for UI TTFT test | Report stream and non-stream separately. |
| GPU memory utilization | Start at 0.80 | Raising it may improve KV capacity but reduces headroom. |
| Timeout | Set from SLA and chunk duration | A 30s chunk needs a different timeout than a 2s clip. |

Technical throughput formula:

```text
audio_hours_per_gpu_hour = total_audio_seconds_processed / wall_seconds
```

Pricing can be calculated outside this repo from the measured technical throughput. This repo should stop at latency, success rate, RTF, req/s, GPU utilization, and audio-hours/GPU-hour.

## 6. Evidence Block Template

```text
Environment: <GPU SKU>, <driver>, <CUDA>, <framework versions>
Model: <checkpoint/path>, <precision>, <backend>
Audio set: <N files>, <total duration>, <language mix>, <ground truth source>
Command: <exact command>
Result files: <paths>
Key results: WER/CER/hotword, RTF, P50/P95, success rate
Sizing: audio-hours/GPU-hour, concurrency knee point, failure boundary
Limitations: <what this run does not prove>
```

