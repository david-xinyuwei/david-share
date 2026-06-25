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

## 4. Interpretation Rules

- Do not report WER/CER without ground truth.
- Do not report framework superiority unless input, model, decoding, pipeline, and hardware are controlled.
- Do not treat mock endpoint speed as ASR speed.
- Do not average short and long audio without showing duration buckets.
- Do not turn throughput into business claims until utilization and serving topology are measured.

## 5. Evidence Block Template

```text
Environment: <GPU SKU>, <driver>, <CUDA>, <framework versions>
Model: <checkpoint/path>, <precision>, <backend>
Audio set: <N files>, <total duration>, <language mix>, <ground truth source>
Command: <exact command>
Result files: <paths>
Key results: WER/CER/hotword, RTF, P50/P95, success rate
Limitations: <what this run does not prove>
```

