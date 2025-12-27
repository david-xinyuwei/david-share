# Azure NC RTX Pro 6000 V6 BSE Complete Benchmark Report

> Comprehensive comparison of NC RTX 6000 Pro Blackwell /NC H100 NVL /NC A100 PCIe /NV A10

> For fairness, each test is performed using the same data type across all four GPUs.

---

## Test Environment

### Hardware Configuration

| Config | RTX 6000 Pro Blackwell | H100 NVL | A100 PCIe | A10 |
|--------|------------------------|----------|-----------|-----|
| **GPU Model** | RTX Pro 6000 Blackwell DC-4-96Q | NVIDIA H100 NVL | NVIDIA A100 80GB PCIe | NVIDIA A10-24Q (vGPU) |
| **Architecture** | Blackwell (GB202) | Hopper (GH100) | Ampere (GA100) | Ampere (GA102) |
| **VRAM** | 96 GB GDDR7 | 94 GB HBM3 | 80 GB HBM2e | 24 GB GDDR6 |

### GPU Hardware Unit Descriptions

| Hardware Unit | Function | Typical Applications |
|----------|------|----------|
| **NVDEC** | Video Decode (H.264/H.265/AV1 → raw frames) | Video playback, AI video analysis preprocessing |
| **NVENC** | Video Encode (raw frames → MP4) | Live streaming, video export, cloud gaming |
| **NVJPG** | JPEG hardware-accelerated codec | Batch image processing, training data preprocessing |
| **Tensor Core** | AI matrix multiplication acceleration | LLM, Stable Diffusion, video generation |
| **RT Core** | Ray tracing computation | Game ray tracing, 3D rendering, CAD preview |
| **CUDA Core** | General parallel computing | Foundation of all GPU computing |

### Hardware Unit Configuration Matrix

| Hardware Unit | RTX 6000 Pro Blackwell | H100 NVL | A100 PCIe | A10 |
|----------|------------------------|----------|-----------|-----|
| **NVDEC** (Decoder) | ✅ 4 (Gen6) | ✅ 7 | ✅ 5 | ✅ 2 |
| **NVENC** (Encoder) | ✅ **4 (Gen9, AV1)** | ❌ **None** | ❌ **None** | ✅ 1 (Gen7) |
| **NVJPG** | ✅ Yes | ✅ 7 | ✅ 5 | ❌ No |
| **Tensor Core** | ✅ Gen5 | ✅ Gen4 | ✅ Gen3 | ✅ Gen3 |
| **RT Core** | ✅ **188 (Gen4)** | ❌ **None** | ❌ **None** | ✅ 72 (Gen2) |
| **NVLink** | ❌ None | ✅ Yes | ✅ Yes | ❌ None |

---

## Scenario Support Matrix

### AI Scenarios

| Scenario | Required Hardware | RTX 6000 | H100 | A100 | A10 |
|------|----------|----------|------|------|-----|
| LLM Training (>70B) | Tensor Core + NVLink + Large VRAM | ❌ | ✅ | ✅ | ❌ |
| LLM Fine-tuning (7B-70B) | Tensor Core + Large VRAM | ✅ | ✅ | ✅ | ⚠️ |
| LLM Inference | Tensor Core | ✅ | ✅ | ✅ | ⚠️ |
| AI Image Generation (SD/FLUX) | Tensor Core | ✅ | ✅ | ✅ | ✅ |
| **AI Video Generation (with MP4 output)** | Tensor Core + **NVENC** | ✅ | ❌ | ❌ | ✅ |

### Video/Media Scenarios

| Scenario | Required Hardware | RTX 6000 | H100 | A100 | A10 |
|------|----------|----------|------|------|-----|
| **Video Transcoding** | NVDEC + **NVENC** | ✅ | ❌ | ❌ | ✅ |
| Video Decode Only | NVDEC | ✅ | ✅ | ✅ | ✅ |
| **Live Streaming** | **NVENC** | ✅ | ❌ | ❌ | ✅ |
| Video AI Analysis | NVDEC + Tensor Core | ✅ | ✅ | ✅ | ✅ |

### Gaming/Rendering Scenarios

| Scenario | Required Hardware | RTX 6000 | H100 | A100 | A10 |
|------|----------|----------|------|------|-----|
| **Cloud Gaming** | RT Core + NVENC | ✅ | ❌ | ❌ | ✅ |
| **3D Rendering (Ray Tracing)** | **RT Core** | ✅ | ❌ | ❌ | ✅ |
| Blender Rendering | RT Core | ✅ | ❌ | ❌ | ✅ |
| CAD Real-time Preview | RT Core + CUDA | ✅ | ❌ | ❌ | ✅ |
| VDI (Virtual Desktop) | NVENC + Graphics | ✅ | ❌ | ❌ | ✅ |

### 🎯 Three Key Selection Principles

1. **Need video encoding output?** → Must have NVENC → **Exclude H100 / A100**
2. **Need ray tracing?** → Must have RT Core → **Exclude H100 / A100**
3. **Pure AI computing?** → Check Tensor Core + VRAM + NVLink

---

## 1. Network Configuration Test 

### Test Results

| Item | Standard_NC256ds_xl_RTXPRO6000BSE_v6 |
|------|------------------|
| **NIC Model** | Microsoft Azure Network Adapter (MANA) |
| **Azure Bandwidth Limit** | **100 Gbps** |
| **Measured Bandwidth (Single Stream)** | 30 Gbps |
| **Measured Bandwidth (16 Streams)** | **50 Gbps** |
| **RDMA/RoCE** | ❌ No |
| **InfiniBand** | ❌ No |

### Conclusion

- RTX 6000 VM uses Azure MANA Ethernet, up to 100 Gbps
- No RDMA/InfiniBand support, not suitable for multi-node GPU communication-intensive training

---

## 2. GPU P2P Interconnect Test

### Test Results

| Item | Standard_NC256ds_xl_RTXPRO6000BSE_v6 |
|------|---------------|
| **nvidia-smi topo -p2p** | OK (Hardware level supported) |
| **PyTorch can_device_access_peer()** | **False** (Still achieves ~43 GB/s) |
| **GPU0 → GPU1 BW** | **41.26 GB/s** |
| **GPU1 → GPU0 BW** | **44.46 GB/s** |
| **NCCL AllReduce** | **~43.5 GB/s** |

### P2P Comparison

| GPU Config | P2P Bandwidth | Notes |
|----------|----------|------|
| **RTX 6000 MIG** | ~43 GB/s | PCIe Gen5 |
| **H100 NVL** | ~450 GB/s | NVLink 4.0 direct |
| **A100 PCIe** | ~25 GB/s | PCIe Gen4 |

---

## 3. FP32 Compute Test

### Test Results

| Metric | RTX 6000 Pro Blackwell (MIG) |
|------|------------------------------|
| **Theoretical FP32** | 116.95 TFLOPS |
| **Measured Peak** | **109.20 TFLOPS** |
| **Efficiency** | **93.4%** |
| **SM Count** | 188 |
| **CUDA Cores** | 24,064 |

---

## 4. LLM Inference Test

### Test Configuration

| Parameter | Value |
|------|-----|
| **Model** | microsoft/Phi-3.5-mini-instruct (3.8B) |
| **Inference Engine** | vLLM |
| **Test Tool** | guidellm |

### Test Results

| GPU | Output Tokens/s | Relative Performance |
|-----|-----------------|----------|
| **H100 NVL** | **3083.6** | **100%** (Baseline) |
| **RTX 6000 Blackwell MIG** | **2835.4** | **92.0%** |
| **A100 PCIe** | **2119.6** | **68.7%** |
| **A10 24GB** | **563.1** | **18.3%** |

### Visualization

```
Output Tokens/s (Higher is Better)
════════════════════════════════════════════════════════════
H100 NVL        ██████████████████████████████████████████  3083.6 tok/s (100%)
RTX 6000 BW     ██████████████████████████████████████▌     2835.4 tok/s (92%)
A100 PCIe       ███████████████████████████▍                2119.6 tok/s (69%)
A10 24GB        ███████▎                                    563.1 tok/s (18%)
════════════════════════════════════════════════════════════
```

---


## 4.1 NVFP4 (W4A4) Quantized Inference Benchmark (RTX PRO 6000 Blackwell Exclusive)

> ⚠️ **Blackwell Exclusive**: NVFP4 requires SM120 native FP4 Tensor Core, only supported on RTX PRO 6000 Blackwell

### Background

NVFP4 (NV FP4 W4A4) is a unique advantage of NVIDIA Blackwell architecture:
- **W4A4**: 4-bit weights + 4-bit activations, more aggressive quantization than FP8 (W8A8)
- **Blackwell Only**: Requires SM100/SM120 native FP4 Tensor Core
- **Memory Savings**: Model size ~35% smaller than FP8 (9.9GB vs 15.3GB for 14B)

### Test Configuration

| Parameter | Value |
|-----------|-------|
| **Model** | Qwen3-14B-NVFP4 vs Qwen3-14B-FP8 (Local pre-quantized) |
| **Quantization** | NVFP4 W4A4 (compressed-tensors) |
| **Framework** | vLLM 0.12.0 (native CUTLASS NVFP4 kernel) |
| **Benchmark Tool** | vLLM 0.12.0 (native CUTLASS NVFP4 kernel) |
| **Workload** | 200 prompts, 512 input tokens, 128 output tokens |

### Test Results

| Precision | Model | Input Tokens | Output Tokens | Time | Output TPS |
|-----------|-------|-------------:|-------------:|-----:|----------:|
| **NVFP4 (W4A4)** | Qwen3-14B-NVFP4 | 102,400 | 25,600 | 9.22s | **2,777 tok/s** |
| **FP8 (W8A8)** | Qwen3-14B-FP8 | 102,400 | 25,600 | 12.75s | **2,009 tok/s** |

### Performance Comparison

\`\`\`
NVFP4 vs FP8 Output Throughput (Qwen3-14B, RTX PRO 6000 Blackwell)
═════════════════════════════════════════════════════════════
NVFP4 (W4A4)    ███████████████████████████████████████████  2,777 tok/s (+38%)
FP8 (W8A8)      ████████████████████████████                 2,009 tok/s (baseline)
═════════════════════════════════════════════════════════════
\`\`\`

### Key Metrics Comparison

| Metric | NVFP4 (W4A4) | FP8 (W8A8) | Difference |
|--------|--------------|------------|------------|
| **Output TPS** | **2,777** | 2,009 | **+38%** |
| **Model Size** | **9.9 GB** | 15.3 GB | **-35%** |
| **KV Cache Available** | 65.5 GiB | 60.1 GiB | +9% |
| **Inference Time** | **9.22s** | 12.75s | **-28%** |

### Pitfalls ⚠️

| Issue | Cause | Solution |
|-------|-------|----------|
| NVFP4 model loads as BF16 | SGLang 0.5.x doesn't recognize NVFP4 format | Use vLLM instead |
| vLLM 0.13.0 shows "platform does not support cutlass NVFP4" | vLLM 0.13.0 removed SM120 NVFP4 support | **Downgrade to vLLM 0.12.0** |
| FlashInfer 0.5.3 has no fp4 module | Version too old | Compile FlashInfer 0.6.0rc2 |

### Environment Requirements

\`\`\`bash
# Must use vLLM 0.12.0 (0.13.0 doesn't support SM120 NVFP4)
pip install vllm==0.12.0

# Verify NVFP4 support
python -c "from vllm._custom_ops import cutlass_scaled_mm_supports_fp4; print(f'NVFP4 support: {cutlass_scaled_mm_supports_fp4(120)}')"
# Expected output: NVFP4 support: True

# Run benchmark
vllm bench serve \
  --backend openai-chat \
  --base-url http://localhost:8000 \
  --endpoint /v1/chat/completions \
  --model /path/to/model \
  --dataset-name random \
  --random-input-len 1024 \
  --random-output-len 256 \
  --num-prompts 100 \
  --max-concurrency 16 \
  --request-rate inf
\`\`\`

### Conclusions

1. **NVFP4 is 38% faster than FP8** - Blackwell native FP4 Tensor Core acceleration is significant
2. **Lower latency across the board** - TTFT 40% faster, TPOT 33% faster
3. **Lower memory usage** - Smaller model = larger KV Cache = higher concurrency potential
4. **Blackwell exclusive advantage** - H100/A100 cannot use NVFP4, only RTX PRO 6000 Blackwell supports it
5. **Version sensitive** - Must use vLLM 0.12.0, 0.13.0 removed SM120 support

> 💡 **Recommendation**: On RTX PRO 6000 Blackwell, prefer NVFP4 quantized models for **38% extra performance** over FP8.

---

# Run benchmark
vllm bench serve \
  --backend openai-chat \
  --base-url http://localhost:8000 \
  --endpoint /v1/chat/completions \
  --model /path/to/model \
  --dataset-name random \
  --random-input-len 1024 \
  --random-output-len 256 \
  --num-prompts 100 \
  --max-concurrency 16 \
  --request-rate inf
\`\`\`

### Conclusions

1. **NVFP4 is 38% faster than FP8** - Blackwell native FP4 Tensor Core acceleration is significant
2. **Lower latency across the board** - TTFT 40% faster, TPOT 33% faster
3. **Lower memory usage** - Smaller model = larger KV Cache = higher concurrency potential
4. **Blackwell exclusive advantage** - H100/A100 cannot use NVFP4, only RTX PRO 6000 Blackwell supports it
5. **Version sensitive** - Must use vLLM 0.12.0, 0.13.0 removed SM120 support

> 💡 **Recommendation**: On RTX PRO 6000 Blackwell, prefer NVFP4 quantized models for **38% extra performance** over FP8.

---


## 4.1.1 Tensor Parallel (TP=1 vs TP=2) Benchmark

> ⚠️ **RTX PRO 6000 Dual GPU**: Testing when TP=2 provides benefits over TP=1

### Background

When a single RTX PRO 6000 cannot fully utilize both GPUs for a small model, or when a large model benefits from tensor parallelism across 2 GPUs:
- **TP=1**: Single GPU inference, model fits in one GPU
- **TP=2**: Tensor parallel across 2 GPUs, model weights split across GPUs

### Test Configuration

| Parameter | Value |
|-----------|-------|
| **Framework** | vLLM 0.12.0 |
| **Small Model** | Qwen3-14B-FP8 (for TP overhead comparison) |
| **Large Model** | Qwen2.5-VL-72B-Instruct-FP8-dynamic |
| **Benchmark Tool** | vLLM 0.12.0 (native CUTLASS NVFP4 kernel) |
| **Workload** | 64 prompts, 512 input tokens, 256 output tokens, concurrency=16 |
| **KV Cache** | FP8 |

### Small Model Results (Qwen3-14B-FP8)

| Configuration | Output Throughput | TTFT | TPOT |
|---------------|------------------:|-----:|-----:|
| **TP=1** | **276.02 tok/s** | 1036 ms | 49.40 ms |
| **TP=2** | 266.19 tok/s | 1252 ms | 52.16 ms |
| **Difference** | **-3.6%** | +21% slower | +5.6% slower |

> ⚠️ **14B model is too small for TP=2 benefit** - The communication overhead between GPUs outweighs the parallelism benefit.

### Large Model Results (Qwen2.5-VL-72B-FP8)

| Configuration | Output Throughput | TTFT | TPOT |
|---------------|------------------:|-----:|-----:|
| **TP=1** | 232.02 tok/s | 1695 ms | 62.57 ms |
| **TP=2** | **294.77 tok/s** | 1801 ms | 47.42 ms |
| **Difference** | **+27.0%** | +6.3% slower | **-24.2% faster** |


### Robustness Verification (Day 2 Retest)

To verify the stability and reproducibility of benchmark results, we re-ran the same tests on Day 2:

| Metric | Day 1 TP=1 | Day 2 TP=1 | Variance | Day 1 TP=2 | Day 2 TP=2 | Variance |
|--------|-----------|-----------|----------|-----------|-----------|----------|
| **Output Throughput** | 232.02 tok/s | 231.50 tok/s | **-0.2%** | 294.77 tok/s | 296.46 tok/s | **+0.6%** |
| **TPOT** | 62.57 ms | 62.40 ms | -0.3% | 47.42 ms | 46.76 ms | -1.4% |
| **TTFT** | 1695 ms | 1779 ms | +5.0% | 1801 ms | 1891 ms | +5.0% |

> ✅ **Conclusion: Results are highly stable** - Throughput variance <1%, demonstrating excellent reproducibility.

### GPU-to-GPU Communication Bandwidth (PCIe Gen5, No NVLink)

During TP=2 inference, the two GPUs communicate via PCIe. Measured P2P bandwidth:

| Direction | Bandwidth | Notes |
|-----------|-----------|-------|
| **GPU0 → GPU1** | **41.26 GB/s** | PCIe Gen5 x16 |
| **GPU1 → GPU0** | **44.46 GB/s** | PCIe Gen5 x16 |
| **NCCL AllReduce** | **~43.5 GB/s** | Bidirectional aggregate |

> ⚠️ **PCIe Gen5 (~43 GB/s unidirectional) bandwidth is limited** - NVLink provides ~450 GB/s unidirectional (~10x faster). PCIe is the bottleneck for TP>1. 72B models still achieve 27% improvement, but larger models or TP>2 may be constrained.

### Visualization

```
TP=1 vs TP=2 Output Throughput Comparison
═════════════════════════════════════════════════════════════
Qwen3-14B (Small Model - TP overhead dominates)
  TP=1    ██████████████████████████████████████████  276.02 tok/s (baseline)
  TP=2    ████████████████████████████████████████▌   266.19 tok/s (-3.6%)

Qwen2.5-VL-72B (Large Model - TP benefit realized)
  TP=1    ██████████████████████████████████████      232.02 tok/s (baseline)
  TP=2    ████████████████████████████████████████████████  294.77 tok/s (+27%)
═════════════════════════════════════════════════════════════
```

### Key Findings

1. **Model size determines TP benefit**
   - Small models (<30B): TP=2 adds overhead, **use TP=1**
   - Large models (>70B): TP=2 provides **25-35% speedup**

2. **TPOT (Time per Output Token) improves significantly with TP=2**
   - 72B model: 62.57ms → 47.42ms (**24% faster per token**)
   - This is due to parallel matrix operations across 2 GPUs

3. **TTFT (Time to First Token) slightly increases with TP=2**
   - Cross-GPU synchronization adds ~100ms latency
   - Acceptable tradeoff for higher throughput

### Recommendations

| Model Size | Recommended Config | Reason |
|------------|-------------------|--------|
| **<30B parameters** | **TP=1** | Communication overhead > parallelism benefit |
| **30B-70B parameters** | Test both | Depends on specific model architecture |
| **>70B parameters** | **TP=2** | 25-35% throughput improvement |

> 💡 **Rule of thumb**: Only use TP=2 when a single GPU cannot fit the model comfortably, or when the model is large enough (>70B) to benefit from parallel computation.

---
## 4.2 SGLang BF16/FP8 Three-GPU Comparison (200 Concurrent)

> Test Date: 2025-12 | Framework: SGLang 0.5.6.post2 + FlashInfer 0.5.3

### Background

Comparing H100, RTX PRO 6000, and A100 GPUs under **high concurrency (200 prompts)** for BF16 vs FP8 inference performance:

- **BF16**: Original precision, no quantization
- **FP8**: Pre-quantized model (RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic)
- **Native FP8 Tensor Core**: H100 (Hopper) and RTX PRO 6000 (Blackwell) support native FP8, A100 requires Marlin fallback

### Test Configuration

| Parameter | Value |
|-----------|-------|
| **Framework** | SGLang 0.5.6.post2 |
| **FlashInfer** | 0.5.3 |
| **Model (BF16)** | Qwen/Qwen2.5-14B-Instruct |
| **Model (FP8)** | RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic |
| **Concurrency** | 200 prompts |
| **Input** | 512 tokens |
| **Output** | 128 tokens |
| **request_rate** | inf (stress test) |
| **random_range_ratio** | 0.0 (fixed length) |

### Test Results

| GPU | BF16 (tok/s) | FP8 (tok/s) | FP8 vs BF16 | FP8 Implementation |
|-----|-------------:|------------:|:-----------:|:------------------:|
| **H100 NVL 96GB** | 2,197 | 2,681 | **+22%** | Native FP8 Tensor Core |
| **RTX PRO 6000 96GB** | 1,579 | 2,353 | **+49%** | Native FP8 Tensor Core |
| **A100 80GB PCIe** | 1,196 | - | - | Marlin fallback |

> ⚠️ **A100 Note**: A100 SGLang 200 concurrent only has BF16 test data, FP8 test not saved. A100 lacks native FP8 Tensor Core, requires Marlin kernel fallback.

### Visualization

```
SGLang 200 Concurrent BF16 Throughput (tok/s)
═════════════════════════════════════════════════════════════
H100 NVL        ████████████████████████████████████████████  2,197 tok/s
RTX PRO 6000    ████████████████████████████████              1,579 tok/s
A100 PCIe       ████████████████████████                      1,196 tok/s
═════════════════════════════════════════════════════════════

SGLang 200 Concurrent FP8 Throughput (tok/s)
═════════════════════════════════════════════════════════════
H100 NVL        ████████████████████████████████████████████  2,681 tok/s
RTX PRO 6000    ████████████████████████████████████████      2,353 tok/s
A100 PCIe       (not tested)
═════════════════════════════════════════════════════════════
```

### Test Method

```bash
# SGLang server start (BF16)
python -m sglang.launch_server \
  --model-path Qwen/Qwen2.5-14B-Instruct \
  --dtype bfloat16 \
  --tp 1 --port 30000

# SGLang server start (FP8, RTX PRO 6000 best config)
python -m sglang.launch_server \
  --model-path RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic \
  --attention-backend triton \
  --kv-cache-dtype fp8_e4m3 \
  --tp 1 --port 30000

# Benchmark command
python -m sglang.bench_serving --backend sglang \
  --dataset-name random --num-prompts 200 \
  --random-input-len 512 --random-output-len 128 \
  --random-range-ratio 0.0 \
  --host 127.0.0.1 --port 30000
```

### Pitfalls ⚠️

| Issue | Cause | Solution |
|-------|-------|----------|
| **3x throughput difference** | `--random-range-ratio` defaults to 1.0 (random length) | Use **0.0** for benchmark (fixed length) |
| **Runtime quantization OOM** | `--quantization fp8` OOM at startup | Must use **pre-quantized FP8 model** |
| **FlashInfer version** | v0.2.0 is 1.5x slower than FA2 | Use **v0.5.3+** |
| **Cannot reproduce results** | total_input_tokens differs | **Compare JSON output total_input_tokens first** |

### Key Findings

1. **Native FP8 support makes a significant difference**
   - H100/RTX PRO 6000: Native FP8 Tensor Core, 22-49% speedup
   - A100: Marlin fallback, ~29% speedup (based on vLLM 50 concurrent data)

2. **RTX PRO 6000 has the highest FP8 speedup (+49%)**
   - Blackwell architecture has more aggressive FP8 optimization
   - From 1,579 to 2,353 tok/s

3. **Test parameters have huge impact**
   - `random_range_ratio=0.0`: Tests cache-friendly limit (Radix Cache hit)
   - `random_range_ratio=1.0`: Tests real workload scenario (no cache)

---

## 5. SFT Full Fine-tuning Test

### Test Configuration

| Parameter | Value |
|------|-----|
| **Model** | Qwen/Qwen3-8B-Base (8.19B params) |
| **Training Type** | Full Fine-Tuning |
| **Precision** | BF16 |

### Test Results

| GPU | Training Time | Speed (s/step) | vs H100 |
|-----|---------|--------------|-----------|
| **H100 NVL** | **19.74 min** | **11.84** | **100%** |
| **RTX 6000 MIG** | 25.14 min | 15.09 | 78.5% |
| **A100 PCIe** | 36.98 min | 22.19 | 53.4% |

---

## 6. FLUX Image Generation Test

### Test Configuration

| Parameter | Value |
|------|-----|
| **Model** | FLUX.1 schnell (12B params) |
| **Resolution** | 1024×1024 |
| **Inference Steps** | 4 steps |

### Test Results

| GPU | Avg Time | Images/min | Relative Performance |
|-----|---------|-----------|----------|
| **H100 NVL** | **1.25s** | **47.8 ** | **100%** |
| **RTX 6000** | **1.42s** | **42.3 ** | **88%** |
| **A100 PCIe** | **2.16s** | **27.8 ** | **58%** |
| **A10 24GB** | ❌ **OOM** | - | - |

---

## 7. Blender Rendering Test

### Test Results

| GPU | **Pure Render Time** | Relative Performance |
|-----|---------------|----------|
| **RTX 6000** | **~2.15s** | **3.76x** ✅ |
| **A10** | **~8.08s** | 1.00x (Baseline) |

> **Note**: H100/A100 have no RT Core, not suitable for ray tracing rendering

---

## 8. NVENC Video Encoding Test

### Single Stream Test Results (H.264)

| Preset | RTX 6000 | A10 | Winner |
|--------|----------|-----|------|
| **P1 (Fastted)** | 167 fps | 197 fps | A10 +18% |
| **P4 (Balance)** | **129 fps** | 97 fps | **RTX 6000 +33%** ✅ |
| **P7 (High quality)** | **87 fps** | 60 fps | **RTX 6000 +45%** ✅ |

### Multi-Stream Parallel Test

| Parallel Streams | RTX 6000 | A10 | Ratio |
|---------|----------|-----|------|
| 1 stream | 98 fps | 87 fps | 1.13x |
| 4 streams | **313 fps** | 87 fps* | **3.6x** |
| 12 streams | **348 fps** | 87 fps* | **4.0x** |

> *A10 vGPU mode only supports single stream parallel  
> **Note**: H100/A100 have no NVENC, cannot perform this test

---

## Four GPU Comprehensive Comparison



### 🏆 Scenario Recommendations

| Use Case | Recommended GPU | Reason |
|----------|----------|------|
| **3D Rendering/Animation** | 🥇 **RTX 6000** | RT Core crushing advantage, H100/A100 not supported |
| **AI Image Gen (Performance)** | 🥇 H100 > 🥈 RTX 6000 > 🥉 A100 | H100 fastest, RTX 6000 52% faster than A100 |
| **Video Transcode (Multi-stream)** | 🥇 **RTX 6000** > 🥈 A10 | 4x throughput advantage, H100/A100 not supported |
| **AI Video Generation (Includes MP4 Output)** | 🥇 **RTX 6000** > 🥈 A10 | H100/A100 None NVENC，Could not output vedio |
| **LLM Reasoning (Performance Focus)** | 🥇 H100 > 🥈 RTX 6000 > 🥉 A100 | H100 is fastest ，RTX 6000 is 92% |
| **LLM Training (>70B)** | 🥇 H100 > 🥈 A100 | Requires NVLink multi-GPU, RTX 6000 not supported |
| **SFT Fine-tuning (Performance)** | 🥇 H100 > 🥈 RTX 6000 > 🥉 A100 | H100 fastest, RTX 6000 47% faster than A100 |
| **Cloud Gaming/VDI** | 🥇 **RTX 6000** > 🥈 A10 | RT Core + NVENC, H100/A100 not supported |
| **Live Streaming** | 🥇 **RTX 6000** > 🥈 A10 | NVENC Gen9 vs Gen7, H100/A100 no NVENC |

### Positioning Summary

| GPU | Positioning | Advantages | Limitations |
|-----|------|------|------|
| **RTX 6000** | All-round Professional | Complete hardware units, full pipeline, 96GB GDDR7, 128 vCPU | No NVLink |
| **H100** | Pure AI Compute | Strongest Tensor Core, 94GB HBM3, NVLink | **No NVENC, No RT Core** |
| **A100** | AI Training/Inference | Mature ecosystem, 80GB HBM2e, NVLink | **No NVENC, No RT Core** |
| **A10** | Inference/Graphics/VDI | Has NVENC + RT Core, supports GPU partitioning, 440GB memory | Small VRAM (24GB) |



---

## 📦 Repository Structure

```
NC-RTX-Pro-6000V6-BSE-Benchmark/
├── README.md                      # English documentation (this file)
├── README-CN.md                   # Chinese Documentation
├── benchmark_tp_comparison.py     # TP=1 vs TP=2 benchmark script
├── gpu_p2p_bandwidth_test.py      # GPU P2P bandwidth test
└── requirements.txt               # Python dependencies
```

---

## 🚀 Quick Start

### Prerequisites

```bash
# Create conda environment (recommended)
conda create -n vllm012 python=3.11
conda activate vllm012

# Install dependencies
pip install -r requirements.txt
```

### Run TP Benchmark

Compare Tensor Parallel performance (TP=1 vs TP=2):

```bash
# TP=1 test (single GPU)
python benchmark_tp_comparison.py \
    --model Qwen/Qwen2.5-VL-72B-Instruct-FP8 \
    --tp 1 \
    --port 8000

# TP=2 test (dual GPU)
python benchmark_tp_comparison.py \
    --model Qwen/Qwen2.5-VL-72B-Instruct-FP8 \
    --tp 2 \
    --port 8001
```

### Test GPU P2P Bandwidth

Measure GPU-to-GPU communication bandwidth:

```bash
python gpu_p2p_bandwidth_test.py
```

Expected output on RTX PRO 6000 (PCIe Gen5, no NVLink):
- GPU0 → GPU1: ~41-44 GB/s
- GPU1 → GPU0: ~41-44 GB/s

---

## 📊 Scripts Description

| Script | Purpose | Key Metrics |
|--------|---------|-------------|
| `benchmark_tp_comparison.py` | Compare TP=1 vs TP=2 inference performance | Output throughput (tok/s), TTFT, TPOT |
| `gpu_p2p_bandwidth_test.py` | Measure GPU P2P bandwidth | Bandwidth (GB/s), NVLink/PCIe detection |

---
