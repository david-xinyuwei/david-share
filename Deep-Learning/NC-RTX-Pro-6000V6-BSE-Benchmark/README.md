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

## 5. SFT Full Fine-tuning Test

### Test Configuration

| Parameter | Value |
|------|-----|
| **Model** | Qwen/Qwen3-8B-Base (8.19B 参数) |
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
| **Model** | FLUX.1 schnell (12B 参数) |
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
| 1 流 | 98 fps | 87 fps | 1.13x |
| 4 流 | **313 fps** | 87 fps* | **3.6x** |
| 12 流 | **348 fps** | 87 fps* | **4.0x** |

> *A10 vGPU mode only supports single stream parallel  
> **Note**: H100/A100 have no NVENC, cannot perform this test

---

## Four GPU Comprehensive Comparison

### 📊 Performance Summary Table

| Test Item | RTX 6000 | H100 NVL | A100 PCIe | A10 | RTX 6000 Assessment |
|----------|----------|----------|-----------|-----|---------------|
| **LLM Inference** (tok/s) | 2835.4 | **3083.6** | 2119.6 | 563.1 | 92% of H100 |
| **SFT Fine-tuning** (s/step) | 15.09 | **11.84** | 22.19 | N/A | 47% faster than A100 |
| **FLUX Image Gen** (img/min) | 42.3 | **47.8** | 27.8 | ❌ OOM | 52% faster than A100 |
| **Blender Rendering** | **~2.15s** | ❌ No RT | ❌ No RT | ~8.08s | 3.76x of A10 |
| **NVENC Multi-stream** | **~350 fps** | ❌ None | ❌ None | 87 fps | 4x of A10 |
| **VRAM Capacity** | 96 GB | 94 GB | 80 GB | 24 GB | Largest |

### 💻 Azure VM Configuration Comparison (Single GPU)

| VM SKU | GPU | vCPU | Memory | GPU VRAM |
|--------|-----|------|------|----------|
| **Standard_NC128lds_xl_RTXPRO6000BSE_v6** | RTX 6000 Pro Blackwell | 128 | 256 GB | 96 GB GDDR7 |
| **NC40ads H100 v5** | H100 NVL | 40 | 320 GB | 94 GB HBM3 |
| **NC24ads A100 v4** | A100 PCIe | 24 | 220 GB | 80 GB HBM2e |
| **NV36ads A10 v5** | A10 | 36 | 440 GB | 24 GB GDDR6 |

### 💰 Price-Performance Analysis

> Price-performance index based on Azure Pay-As-You-Go single-GPU VM pricing, **A100 as baseline (1.00)**

| Metric | RTX 6000 | H100 NVL | A100 PCIe | A10 |
|------|----------|----------|-----------|-----|
| **LLM Inference Price-Perf** | **1.15** | 0.78 | 1.00 | 0.30 |
| **SFT Fine-tuning Price-Perf** | **1.18** | 0.86 | 1.00 | N/A |
| **FLUX Image Gen Price-Perf** | **1.14** | 0.90 | 1.00 | N/A |

**Analysis:**
- **RTX 6000 best price-performance**: LLM inference price-perf 15% higher than A100, 47% higher than H100
- **RTX 6000 most vCPUs**: 128 vCPU, suitable for data preprocessing, CPU parallel tasks
- **H100 strongest performance but average price-perf**: High price, suitable for maximum performance scenarios
- **A100 balanced price-performance**: Mature ecosystem, moderate price-perf
### 🏆 Scenario Recommendations

| Use Case | Recommended GPU | Reason |
|----------|----------|------|
| **3D Rendering/Animation** | 🥇 **RTX 6000** | RT Core crushing advantage, H100/A100 not supported |
| **AI Image Gen (Performance)** | 🥇 H100 > 🥈 RTX 6000 > 🥉 A100 | H100 fastest, RTX 6000 52% faster than A100 |
| **AI Image Gen (Price-Perf)** | 🥇 **RTX 6000** > 🥈 A100 > 🥉 H100 | RTX 6000 best price-perf (1.14) |
| **Video Transcode (Multi-stream)** | 🥇 **RTX 6000** > 🥈 A10 | 4x throughput advantage, H100/A100 not supported |
| **AI Video Generation (Includes MP4 Output)** | 🥇 **RTX 6000** > 🥈 A10 | H100/A100 None NVENC，Could not output vedio |
| **LLM Reasoning (Performance Focus)** | 🥇 H100 > 🥈 RTX 6000 > 🥉 A100 | H100 is fastest ，RTX 6000 is 92% |
| **LLM Inference (Price-Perf)** | 🥇 **RTX 6000** > 🥈 A100 > 🥉 H100 | RTX 6000 best price-perf (1.15) |
| **LLM Training (>70B)** | 🥇 H100 > 🥈 A100 | Requires NVLink multi-GPU, RTX 6000 not supported |
| **SFT Fine-tuning (Performance)** | 🥇 H100 > 🥈 RTX 6000 > 🥉 A100 | H100 fastest, RTX 6000 47% faster than A100 |
| **SFT Fine-tuning (Price-Perf)** | 🥇 **RTX 6000** > 🥈 A100 > 🥉 H100 | RTX 6000 best price-perf (1.18) |
| **Cloud Gaming/VDI** | 🥇 **RTX 6000** > 🥈 A10 | RT Core + NVENC, H100/A100 not supported |
| **Live Streaming** | 🥇 **RTX 6000** > 🥈 A10 | NVENC Gen9 vs Gen7, H100/A100 no NVENC |

### Positioning Summary

| GPU | Positioning | Advantages | Limitations |
|-----|------|------|------|
| **RTX 6000** | All-round Professional | Complete hardware units, full pipeline, 96GB GDDR7, 128 vCPU | No NVLink |
| **H100** | Pure AI Compute | Strongest Tensor Core, 94GB HBM3, NVLink | **No NVENC, No RT Core** |
| **A100** | AI Training/Inference | Mature ecosystem, 80GB HBM2e, NVLink | **No NVENC, No RT Core** |
| **A10** | Inference/Graphics/VDI | Has NVENC + RT Core, supports GPU partitioning, 440GB memory | Small VRAM (24GB) |

