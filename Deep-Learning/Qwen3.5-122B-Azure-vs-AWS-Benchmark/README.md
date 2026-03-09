    

# Qwen3.5-122B-A10B-FP8 Benchmark Reproduction Guide

> Reproducible benchmark for Qwen3.5-122B-A10B-FP8 using SGLang. Used for Azure vs AWS comparison testing.

---

## 1. Environment

| Item             | Version                                                                      |
| ---------------- | ---------------------------------------------------------------------------- |
| **Model**  | [Qwen/Qwen3.5-122B-A10B-FP8](https://huggingface.co/Qwen/Qwen3.5-122B-A10B-FP8) |
| **OS**     | Ubuntu 24.04 LTS                                                             |
| **Python** | 3.11                                                                         |
| **Engine** | SGLang (main branch)                                                         |
| **NVIDIA Driver** | 590.48                                                                  |
| **CUDA**   | 12.8 (bundled with SGLang/PyTorch)                                           |
| **PyTorch** | 2.9.1+cu128 (auto-installed by SGLang)                                      |
| **CuDNN**  | 9.16.0.29                                                                    |

## 2. Install

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.bashrc

# Create env
uv venv /root/sglang-env --python 3.11
source /root/sglang-env/bin/activate

# Install SGLang (must be main branch for Qwen3.5)
uv pip install 'sglang[all]@git+https://github.com/sgl-project/sglang.git#subdirectory=python'
uv pip install nvidia-cudnn-cu12==9.16.0.29
```

## 3. Download Model

```bash
pip install huggingface_hub[cli]
huggingface-cli download Qwen/Qwen3.5-122B-A10B-FP8 --local-dir /root/models/Qwen3.5-122B-A10B-FP8
```

## 4. Start Server

```bash
source /root/sglang-env/bin/activate

python3 -u -m sglang.launch_server \
    --model-path /root/models/Qwen3.5-122B-A10B-FP8 \
    --served-model-name Qwen3.5-122B-A10B-FP8 \
    --host 0.0.0.0 --port 8000 \
    --tp-size <GPU_COUNT> \
    --tool-call-parser qwen3_coder \
    --reasoning-parser qwen3 \
    --trust-remote-code \
    --mem-fraction-static 0.90 \
    --chunked-prefill-size 8192 \
    --context-length 4096 \
    --kv-cache-dtype fp8_e4m3 \
    --num-continuous-decode-steps 2
```

> Replace `<GPU_COUNT>` with actual GPU count (e.g., `2` for 2×H100, `4` for 4×RTX PRO 6000).

Startup takes ~10 min (DeepGEMM warmup + CUDA graph capture). Wait for `"The server is fired up and ready to roll!"`.

## 5. Run Benchmark

```bash
# Full test: ITL + concurrency 1→512 + Function Calling + stability
python3 scripts/sglang_bench_122b.py --url http://localhost:8000 --mode all --max-concurrency 512 --runs 3

# Performance only
python3 scripts/sglang_bench_122b.py --url http://localhost:8000 --mode perf --max-concurrency 512 --runs 3

# ITL only (single request)
python3 scripts/sglang_bench_122b.py --url http://localhost:8000 --mode itl

# Function Calling only
python3 scripts/sglang_bench_122b.py --url http://localhost:8000 --mode func
```

## 6. Test Config

| Parameter            | Value                                 |
| -------------------- | ------------------------------------- |
| Input tokens         | 1,024                                 |
| Output tokens        | 1,024                                 |
| Stream               | true                                  |
| Thinking mode        | disabled                              |
| Runs per concurrency | 3 (median)                            |
| Concurrency levels   | 1, 2, 4, 8, 16, 32, 64, 128, 256, 512 |

## 7. Metrics to Collect

- **TTFT (ms)** — Time to First Token
- **ITL avg / P50 / P99 (ms)** — Inter-Token Latency (single request, `--mode itl`)
- **Tokens/s** — Throughput at each concurrency
- **QPS** — Queries per Second
- **Function Calling** — 5/5 pass?
- **nvidia-smi** — GPU memory used/total
- **Engine log** — `max_running_requests` and `max_total_num_tokens`

## 8. Azure Results (2×H100 NVL 94GB, TP=2, SGLang)

**ITL (1024→1024, single request):**

|  TTFT  | ITL avg | ITL P50 | ITL P99 |  TPS  |
| :----: | :-----: | :-----: | :-----: | :---: |
| 102 ms | 8.0 ms | 8.0 ms | 8.1 ms | 125.4 |

**Concurrency sweep (1024→1024, 3 runs median):**

|  C  | TTFT (ms) | Tokens/s |  QPS  |
| :-: | :-------: | :------: | :---: |
|  1  |    103    |  111.8  | 1.08 |
|  2  |    114    |  184.7  | 1.70 |
|  4  |    138    |  293.4  | 2.46 |
|  8  |    218    |  439.2  | 3.91 |
| 16 |    167    |  699.7  | 6.51 |
| 32 |    196    |  937.9  | 9.17 |
| 64 |   1,075   | 1,111.5 | 10.24 |
| 128 |   6,225   | 1,010.9 | 9.35 |
| 256 |  10,925  | 1,013.2 | 9.25 |
| 512 |  10,518  | 1,004.8 | 9.46 |

Function Calling: 5/5 ✅ | Stability: 516/516 ✅

---

**Author**: Xinyu Wei (魏新宇)
