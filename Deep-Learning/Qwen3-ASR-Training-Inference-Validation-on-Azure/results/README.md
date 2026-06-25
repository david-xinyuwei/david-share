# Results Directory

This directory stores reproducible JSON outputs from public smoke tests and local harness regressions.

| File | Meaning |
|---|---|
| `harness_test_results.json` | Deterministic local regression suite for scripts |
| `qwen3_asr_0_6b_official_sample_v2.json` | Public Qwen3-ASR short-sample smoke test |
| `qwen3_asr_official_multiround_summary.json` | Three-round public sample summary |
| `gemma3n_h100_route_status.json` | Gemma 3n E2B-it route status: weights downloaded, official HF API path prepared, clean-env smoke JSON not yet collected |
| `multiround/*.json` | Individual public sample rounds |
| `benchmark_endpoint_mock_success.json` | Mock HTTP 200 endpoint run |
| `benchmark_endpoint_mock_failure.json` | Mock HTTP 503 endpoint run |

Do not add customer audio, transcripts, endpoint responses, or private benchmark data to this public directory.

