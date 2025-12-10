# Azure NC/NV GPU VM Selection Guide for Video, Image, and AI Workloads

> Understanding the hardware essence behind GPU selection for different scenarios

**Author**: Xinyu Wei (魏新宇) | AI Architect
**Last Updated**: December 2025

---

## 📖 Table of Contents

1. [Core Concept: GPU Is Not Just &#34;Compute Power&#34;](#core-concept-gpu-is-not-just-compute-power)
2. [Six Hardware Units Explained](#six-hardware-units-explained)
3. [GPU Hardware Configuration Comparison](#gpu-hardware-configuration-comparison)
4. [Scenario × GPU Support Matrix](#scenario--gpu-support-matrix)
5. [Azure GPU VM Series](#azure-gpu-vm-series)
6. [Selection Decision Tree](#selection-decision-tree)
7. [Case Studies](#case-studies)

---

## Core Concept: GPU Is Not Just "Compute Power"

### Common Misconceptions

| Misconception                           | Reality                                                                   |
| --------------------------------------- | ------------------------------------------------------------------------- |
| "GPU = TFLOPS"                          | TFLOPS only measures Tensor/CUDA Core performance, not overall capability |
| "More VRAM = Can run anything"          | Can load ≠ Can complete the full pipeline (may lack encoder for output)  |
| "Data center GPU = Best for everything" | NC H100 cannot do video transcoding, NV A10 can                           |

### The Right Mental Model

**GPU = A combination of specialized hardware units**

```
┌─────────────────────────────────────────────────────────────────┐
│                         NVIDIA GPU                               │
├─────────────────┬─────────────────────┬─────────────────────────┤
│   📥 Decode/In  │     🧠 Compute       │      📤 Encode/Out      │
├─────────────────┼─────────────────────┼─────────────────────────┤
│  NVDEC (Video)  │  CUDA Core (General)│   NVENC (Video)         │
│  NVJPG (Image)  │  Tensor Core (AI)   │   NVJPG (Image)         │
│                 │  RT Core (RayTrace) │                         │
└─────────────────┴─────────────────────┴─────────────────────────┘
```

> 💡 **Note**: NVDEC/NVENC/NVJPG can be used for both input (decode) and output (encode).
> For example: In AI video generation, the input could be an encoded reference video (needs NVDEC to decode), and output needs NVENC to encode to MP4.

**Key Insight**: Different GPUs have different combinations of hardware units, which determines what they can and cannot do.

---

## Six Hardware Units Explained

### 1. NVDEC - Video Decoder

| Attribute           | Description                                               |
| ------------------- | --------------------------------------------------------- |
| **Function**  | Decode compressed video (H.264/H.265/AV1) into raw frames |
| **Analogy**   | Like unzipping a ZIP file                                 |
| **Use Cases** | Video playback, pre-processing for video AI analysis      |

### 2. NVENC - Video Encoder

| Attribute               | Description                                      |
| ----------------------- | ------------------------------------------------ |
| **Function**      | Compress raw frames into video files (MP4, etc.) |
| **Analogy**       | Like compressing into a ZIP file                 |
| **Use Cases**     | Live streaming, video export, cloud gaming       |
| **⚠️ Critical** | **NC H100 / NC A100 do NOT have NVENC!**   |

### 3. NVJPG - JPEG Hardware Engine

| Attribute           | Description                                                        |
| ------------------- | ------------------------------------------------------------------ |
| **Function**  | Hardware-accelerated JPEG encoding/decoding                        |
| **Use Cases** | Image preprocessing pipelines, batch image processing              |
| **Supported** | NC H100 (7 units), NC A100 (5 units), RTX PRO 6000 BSE (Blackwell) |

> ⚠️ **Note**: A10 does NOT support hardware JPEG acceleration, despite being Ampere architecture. nvJPEG hardware acceleration only supports Ampere (A100, A30), Hopper, Ada, and Blackwell.

### 4. Tensor Core

| Attribute             | Description                                                |
| --------------------- | ---------------------------------------------------------- |
| **Function**    | Accelerate matrix multiplication for AI training/inference |
| **Use Cases**   | LLM, Stable Diffusion, video generation AI                 |
| **Generations** | 3rd (Ampere) → 4th (Hopper) → 5th (Blackwell)            |

### 5. RT Core - Ray Tracing Core

| Attribute               | Description                                                             |
| ----------------------- | ----------------------------------------------------------------------- |
| **Function**      | Hardware-accelerated ray tracing calculations                           |
| **Use Cases**     | Game ray tracing, 3D rendering, CAD real-time preview                   |
| **⚠️ Critical** | **NC H100 / NC A100 do NOT have RT Core!**                        |
| **Note**          | NV A10 has 72 RT Cores (2nd Gen), RTX PRO 6000 BSE has 4th Gen RT Cores |

### 6. CUDA Core

| Attribute           | Description                         |
| ------------------- | ----------------------------------- |
| **Function**  | General-purpose parallel computing  |
| **Use Cases** | Foundation of all GPU compute tasks |

---

## GPU Hardware Configuration Comparison

> Note: All specifications are based on Azure VM series offerings.

### Hardware Unit Matrix

| Hardware Unit             | NC H100    | NC A100    | RTX PRO 6000 BSE | NV A10                |
| ------------------------- | ---------- | ---------- | ---------------- | --------------------- |
| **NVDEC** (Decoder) | ✅ 7 units | ✅ 5 units | ✅ 4 units (6th) | ✅ 2 units            |
| **NVENC** (Encoder) | ❌ None    | ❌ None    | ✅ 4 units (9th) | ✅ 1 unit             |
| **NVJPG**           | ✅ 7 units | ✅ 5 units | ✅ Supported     | ❌ Not supported      |
| **Tensor Core**     | ✅ 4th Gen | ✅ 3rd Gen | ✅ 5th Gen       | ✅ 3rd Gen            |
| **RT Core**         | ❌ None    | ❌ None    | ✅ 188 (4th Gen) | ✅ 72 units (2nd Gen) |

> 📝 **Data Sources**: RTX PRO 6000 BSE NVENC/NVDEC/RT Core generations from NVIDIA official specs. H100/A100 NVDEC counts from Azure VM specifications.

### Basic Specifications (Azure VM Series)

| Spec                   | NC H100 (NCads_H100_v5) | NC A100 (NC_A100_v4) | RTX PRO 6000 BSE (NCv6) | NV A10 (NVadsA10_v5) |
| ---------------------- | ----------------------- | -------------------- | ----------------------- | -------------------- |
| **Architecture** | Hopper                  | Ampere               | Blackwell               | Ampere               |
| **VRAM**         | 94GB HBM3               | 80GB HBM2e           | 96GB GDDR7              | 24GB GDDR6           |
| **GPU Count**    | 1-2                     | 1-4                  | 1-2                     | 1/6 - 2              |
| **Max vCPUs**    | 80                      | 96                   | 320                     | 72                   |
| **Max Memory**   | 640 GiB                 | 880 GiB              | 1280 GiB                | 880 GiB              |

### Positioning Summary

| GPU                        | Positioning                | Strengths                                         | Limitations          |
| -------------------------- | -------------------------- | ------------------------------------------------- | -------------------- |
| **NC H100**          | Pure AI compute            | Strongest Tensor Core, 94GB HBM3                  | No NVENC, no RT Core |
| **NC A100**          | AI training/inference      | Mature ecosystem, 80GB HBM2e                      | No NVENC, no RT Core |
| **RTX PRO 6000 BSE** | Full-featured professional | All hardware units, complete pipeline, 96GB GDDR7 | No NVLink            |
| **NV A10**           | Inference/graphics/VDI     | Has NVENC + RT Core, supports fractional GPU      | Smaller VRAM (24GB)  |

---

## Scenario × GPU Support Matrix

### Legend

| Symbol | Meaning                      |
| ------ | ---------------------------- |
| ✅     | Fully supported, recommended |
| ❌     | Not supported                |
| ⚠️   | Works but with limitations   |

### AI Scenarios

| Scenario                              | Required Hardware                 | NC H100 | NC A100 | RTX PRO 6000 BSE | NV A10 |
| ------------------------------------- | --------------------------------- | ------- | ------- | ---------------- | ------ |
| LLM Training (>70B params)            | Tensor Core + NVLink + Large VRAM | ✅      | ✅      | ❌               | ❌     |
| LLM Fine-tuning (7B-70B)              | Tensor Core + Large VRAM          | ✅      | ✅      | ✅               | ⚠️   |
| LLM Inference                         | Tensor Core                       | ✅      | ✅      | ✅               | ✅     |
| AI Image Generation (SD/FLUX)         | Tensor Core                       | ✅      | ✅      | ✅               | ✅     |
| AI Image Generation (batch output)    | Tensor Core + NVJPG               | ✅      | ✅      | ✅               | ⚠️   |
| AI Video Generation (generation only) | Tensor Core + Large VRAM          | ✅      | ✅      | ✅               | ⚠️   |
| AI Video Generation (with MP4 output) | Tensor Core + NVENC               | ❌      | ❌      | ✅               | ✅     |

### Video/Media Scenarios

| Scenario                  | Required Hardware   | NC H100 | NC A100 | RTX PRO 6000 BSE | NV A10 |
| ------------------------- | ------------------- | ------- | ------- | ---------------- | ------ |
| Video Transcoding         | NVDEC + NVENC       | ❌      | ❌      | ✅               | ✅     |
| Video Decode Only         | NVDEC               | ✅      | ✅      | ✅               | ✅     |
| Live Streaming            | NVENC               | ❌      | ❌      | ✅               | ✅     |
| Video Conferencing Encode | NVENC               | ❌      | ❌      | ✅               | ✅     |
| Video AI Analysis         | NVDEC + Tensor Core | ✅      | ✅      | ✅               | ✅     |

### Gaming/Rendering Scenarios

| Scenario               | Required Hardware | NC H100 | NC A100 | RTX PRO 6000 BSE | NV A10 |
| ---------------------- | ----------------- | ------- | ------- | ---------------- | ------ |
| Cloud Gaming           | RT Core + NVENC   | ❌      | ❌      | ✅               | ✅     |
| 3D Games (Ray Tracing) | RT Core           | ❌      | ❌      | ✅               | ✅     |
| DLSS Super Resolution  | Tensor Core       | ✅      | ✅      | ✅               | ✅     |
| DLSS Frame Generation  | Ada/Blackwell     | ❌      | ❌      | ✅               | ❌     |
| Blender Rendering      | RT Core           | ❌      | ❌      | ✅               | ✅     |
| CAD Real-time Preview  | RT Core + CUDA    | ❌      | ❌      | ✅               | ✅     |
| VDI (Virtual Desktop)  | NVENC + Graphics  | ❌      | ❌      | ✅               | ✅     |

> ⚠️ **DLSS Frame Generation Note**: DLSS Frame Generation only supports Ada Lovelace and newer architectures. A10 (Ampere) does NOT support Frame Generation, only DLSS Super Resolution. RTX PRO 6000 BSE (Blackwell) supports DLSS 4 Multi Frame Generation.

### Scientific Computing

| Scenario               | Required Hardware | NC H100 | NC A100 | RTX PRO 6000 BSE | NV A10 |
| ---------------------- | ----------------- | ------- | ------- | ---------------- | ------ |
| General CUDA Computing | CUDA Core         | ✅      | ✅      | ✅               | ✅     |
| FP64 Double Precision  | FP64 Units        | ✅      | ✅      | ⚠️             | ⚠️   |
| Distributed Training   | NVLink            | ✅      | ✅      | ❌               | ❌     |

---

## Azure GPU VM Series

### Available GPU VM Series

| VM Series                        | GPU                                   | GPU Count | VRAM per GPU | Use Cases                                |
| -------------------------------- | ------------------------------------- | --------- | ------------ | ---------------------------------------- |
| **NCads_H100_v5**          | H100 NVL (PCIe)                       | 1-2       | 94GB HBM3    | LLM training/inference, HPC              |
| **NC_A100_v4**             | A100 (PCIe)                           | 1-4       | 80GB HBM2e   | AI training/inference                    |
| **NC RTX PRO 6000 BSE v6** | RTX PRO 6000 Blackwell Server Edition | 1-2       | 96GB GDDR7   | Professional graphics, AI, full pipeline |
| **NVadsA10_v5**            | A10                                   | 1/6 - 2   | 24GB GDDR6   | Inference, graphics, VDI                 |

### VM Selection by Scenario

| Scenario                     | Recommended VM Series               | Reason                          |
| ---------------------------- | ----------------------------------- | ------------------------------- |
| Train large LLM (>70B)       | NCads_H100_v5, ND_A100_v4           | Need large VRAM + NVLink        |
| Fine-tune LLM (7B-70B)       | NC_A100_v4, NCads_H100_v5           | Need sufficient VRAM            |
| LLM Inference service        | NC_A100_v4, NVadsA10_v5             | Balance of performance and cost |
| AI Video Generation + Output | NC RTX PRO 6000 BSE v6, NVadsA10_v5 | Need NVENC for MP4 output       |
| Cloud Gaming                 | NC RTX PRO 6000 BSE v6, NVadsA10_v5 | Need RT Core + NVENC            |
| 3D Rendering                 | NC RTX PRO 6000 BSE v6, NVadsA10_v5 | Need RT Core                    |
| Video Transcoding            | NC RTX PRO 6000 BSE v6, NVadsA10_v5 | Need NVDEC + NVENC              |
| VDI                          | NVadsA10_v5, NC RTX PRO 6000 BSE v6 | Supports fractional GPU         |

---

## Selection Decision Tree

### Three Key Questions

Before selecting a GPU, answer these three questions:

| # | Question                                 | If Yes                           |
| - | ---------------------------------------- | -------------------------------- |
| 1 | **Need video encoding output?**    | → Exclude NC H100 / NC A100     |
| 2 | **Need ray tracing?**              | → Exclude NC H100 / NC A100     |
| 3 | **Model fits in single GPU VRAM?** | No → Need multi-GPU with NVLink |

### Decision Flowchart

```
                    ┌─────────────────────┐
                    │  What's your task?  │
                    └──────────┬──────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
   ┌─────────┐           ┌─────────┐           ┌─────────┐
   │AI Train │           │AI Infer │           │Video/   │
   └────┬────┘           └────┬────┘           │Media    │
        │                     │                └────┬────┘
        ▼                     │                     ▼
   Need NVLink?               │              Need encoding?
        │                     │                     │
    ┌───┴───┐                 │               ┌─────┴─────┐
   Yes     No                 │              Yes         No
    │       │                 │               │           │
    ▼       ▼                 ▼               ▼           ▼
 ┌───────┐ ┌────────┐   ┌──────────┐  ┌───────────┐ ┌───────┐
 │NC H100│ │RTX PRO │   │Check VRAM│  │RTX PRO    │ │NC H100│
 │NC A100│ │6000 BSE│   │& latency │  │6000 BSE   │ │NC A100│
 └───────┘ └────────┘   └──────────┘  │NV A10     │ └───────┘
                                      └───────────┘
```

---

## Case Studies

### Case 1: AI Video Generation Service (CogVideo / Open-Sora Style)

**Requirement**: Build a text-to-video generation service using open-source models like CogVideoX or Open-Sora, output MP4 files

**Pipeline Analysis**:

```
Text Input → DiT Model Inference → Frame Sequence → MP4 Output
              (Tensor Core)         (in VRAM)       (NVENC)
```

**Hardware Requirements**:

- Tensor Core: For AI generation
- Large VRAM: Video models are large (CogVideoX-5B needs ~40GB)
- NVENC: For encoding output

**Conclusion**:

| GPU              | Generation               | Encoding     | Verdict                              |
| ---------------- | ------------------------ | ------------ | ------------------------------------ |
| NC H100          | ✅ Strong                | ❌ No NVENC  | Can generate, cannot directly output |
| NC A100          | ✅ Strong                | ❌ No NVENC  | Can generate, cannot directly output |
| RTX PRO 6000 BSE | ✅ Strong                | ✅ Has NVENC | **End-to-end solution**        |
| NV A10           | ⚠️ Limited VRAM (24GB) | ✅ Has NVENC | May not fit large models             |

### Case 2: Cloud Gaming Platform

**Requirement**: Render games in cloud, stream to user devices

**Pipeline Analysis**:

```
User Input → Game Rendering → Frame Capture → Stream
             (RT Core + CUDA)   (in VRAM)    (NVENC)
```

**Conclusion**:

| GPU              | Ray Tracing    | Encoding      | Verdict                    |
| ---------------- | -------------- | ------------- | -------------------------- |
| NC H100          | ❌ No RT Core  | ❌ No NVENC   | **Not suitable**     |
| NC A100          | ❌ No RT Core  | ❌ No NVENC   | **Not suitable**     |
| RTX PRO 6000 BSE | ✅ 4th Gen     | ✅ 2 encoders | **Excellent choice** |
| NV A10           | ✅ 72 RT Cores | ✅ 1 encoder  | **Good choice**      |

### Case 3: LLM Training (70B Parameters)

**Requirement**: Fine-tune Llama 3 70B model

**VRAM Requirements** (BF16):

- Model parameters: ~140GB
- Optimizer states: ~280GB (Adam)
- Gradients: ~140GB
- Total: Cannot fit in single GPU, need multi-GPU parallel

**Conclusion**:

| GPU              | VRAM  | NVLink  | Verdict                               |
| ---------------- | ----- | ------- | ------------------------------------- |
| NC H100 × 2     | 188GB | ✅      | **Good choice**                 |
| NC A100 × 4     | 320GB | ✅      | **Good choice**                 |
| RTX PRO 6000 BSE | 96GB  | ❌ None | Cannot efficiently do tensor parallel |
| NV A10           | 24GB  | ❌ None | **Not suitable**                |

### Case 4: Video Surveillance AI Analysis

**Requirement**: Real-time analysis of 100 camera feeds

**Pipeline Analysis**:

```
Camera Input → Decode → AI Inference → Results (JSON)
 (H.264/265)  (NVDEC)  (Tensor Core)
```

**Note**: Does NOT need NVENC (output is JSON, not video)

**Conclusion**:

| GPU              | NVDEC Count | Inference         | Verdict                             |
| ---------------- | ----------- | ----------------- | ----------------------------------- |
| NC H100          | 7           | Very strong       | **Best for high concurrency** |
| NC A100          | 5           | Strong            | **Good balance**              |
| RTX PRO 6000 BSE | 4           | Very strong (5th) | **Good choice**               |
| NV A10           | 2           | Moderate          | Lower concurrency                   |

### Case 5: AI Training Data Preprocessing (Batch JPEG Decoding)

**Requirement**: Decode millions of JPEG images for deep learning training dataset

**Pipeline Analysis**:

```
JPEG Images → Hardware Decode → Raw Pixels → Data Augmentation → Training
 (Storage)      (NVJPG)         (GPU Memory)   (CUDA Kernels)    (Tensor Core)
```

**Hardware Requirements**:

- NVJPG: Hardware-accelerated JPEG decode for high throughput
- Large VRAM: Batch processing requires buffer space
- High bandwidth: Feed data fast enough to saturate GPU compute

**Why NVJPG Matters**:

| Method                   | Throughput     | CPU Usage | Use Case                 |
| ------------------------ | -------------- | --------- | ------------------------ |
| CPU decode (libjpeg)     | ~500 img/s     | High      | Legacy systems           |
| GPU software decode      | ~2,000 img/s   | Low       | General purpose          |
| **NVJPG hardware** | ~10,000+ img/s | Near zero | High-throughput training |

**Conclusion**:

| GPU              | NVJPG Support | Units | Verdict                             |
| ---------------- | ------------- | ----- | ----------------------------------- |
| NC H100          | ✅            | 7     | **Best for massive datasets** |
| NC A100          | ✅            | 5     | **Excellent choice**          |
| RTX PRO 6000 BSE | ✅            | Yes   | **Good choice**               |
| NV A10           | ❌            | None  | Fallback to GPU software decode     |

> ⚠️ **Important**: A10 does NOT have NVJPG hardware despite being Ampere architecture. JPEG decoding will use GPU software path (nvJPEG HYBRID backend), which is slower but still functional. nvJPEG hardware acceleration only supports: **Ampere (A100, A30), Hopper, Ada, Blackwell**.

**nvJPEG Backend Modes**:

| Backend                       | Description          | Hardware Used                 |
| ----------------------------- | -------------------- | ----------------------------- |
| `NVJPEG_BACKEND_HARDWARE`   | Pure hardware decode | NVJPG dedicated unit          |
| `NVJPEG_BACKEND_GPU_HYBRID` | GPU-assisted decode  | CUDA Cores (software)         |
| `NVJPEG_BACKEND_HYBRID`     | CPU+GPU hybrid       | CPU for Huffman, GPU for rest |
| `NVJPEG_BACKEND_DEFAULT`    | Auto-select          | Library decides               |

**A10 Fallback Behavior**:

```
nvjpegDecode() called on A10:
    → Check NVJPEG_BACKEND_HARDWARE available?
    → A10: ❌ No NVJPG hardware unit
    → Auto fallback to NVJPEG_BACKEND_GPU_HYBRID
    → (Uses CUDA Cores for software JPEG decode)
```

**Performance Impact**:

| GPU       | NVJPG Hardware | Decode Path           | Relative Performance |
| --------- | -------------- | --------------------- | -------------------- |
| H100/A100 | ✅ Yes         | Hardware accelerated  | **100%**       |
| A10       | ❌ No          | GPU software (HYBRID) | ~20-30%              |
| CPU only  | -              | libjpeg               | ~5%                  |

> For scenarios that don't require ultra-high throughput (e.g., loading a single image before inference), A10 is perfectly adequate.

> 💡 **Note**: NVJPG is for **data preprocessing**, not for **AI image generation**. Stable Diffusion / FLUX output PNG/JPEG using standard libraries, which does NOT require NVJPG hardware.

---

## Quick Reference

### By Scenario

| Scenario                          | Recommended              | Avoid                    |
| --------------------------------- | ------------------------ | ------------------------ |
| LLM Training                      | NC H100, NC A100         | NV A10                   |
| LLM Inference                     | NC H100, NC A100, NV A10 | -                        |
| AI Image Generation               | All GPUs                 | -                        |
| AI Video Generation (with output) | RTX PRO 6000 BSE, NV A10 | NC H100, NC A100         |
| Video Transcoding                 | RTX PRO 6000 BSE, NV A10 | NC H100, NC A100         |
| Cloud Gaming                      | RTX PRO 6000 BSE, NV A10 | NC H100, NC A100         |
| 3D Rendering (Ray Tracing)        | RTX PRO 6000 BSE, NV A10 | NC H100, NC A100         |
| DLSS Frame Generation             | RTX PRO 6000 BSE         | NC H100, NC A100, NV A10 |
| VDI                               | NV A10, RTX PRO 6000 BSE | NC H100, NC A100         |

### By Hardware Requirement

| Requirement           | NC H100 | NC A100 | RTX PRO 6000 BSE | NV A10  |
| --------------------- | ------- | ------- | ---------------- | ------- |
| Tensor Core only      | ✅      | ✅      | ✅               | ✅      |
| NVENC (encoding)      | ❌      | ❌      | ✅               | ✅      |
| RT Core (ray tracing) | ❌      | ❌      | ✅               | ✅      |
| DLSS Frame Generation | ❌      | ❌      | ✅               | ❌      |
| Large VRAM (>48GB)    | ✅ 94GB | ✅ 80GB | ✅ 96GB          | ❌ 24GB |
| NVLink multi-GPU      | ✅      | ✅      | ❌               | ❌      |

---

## Summary: Three Principles

1. **Need video encoding output?** → Must have NVENC → **Exclude NC H100 / NC A100**
2. **Need ray tracing?** → Must have RT Core → **Exclude NC H100 / NC A100** (NV A10 has RT Core)
3. **Pure AI compute?** → Look at Tensor Core + VRAM → **NC H100 > NC A100 > RTX PRO 6000 BSE > NV A10**

---

## References

- [Azure NCads_H100_v5 Series](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/ncadsh100v5-series)
- [Azure NC_A100_v4 Series](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/nca100v4-series)
- [Azure NC RTX PRO 6000 BSE v6 Series](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/nc-rtxpro6000-bse-v6-series)
- [Azure NVadsA10_v5 Series](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/nvadsa10v5-series)
- [NVIDIA Video Codec SDK](https://developer.nvidia.com/video-codec-sdk)
- [NVIDIA H100 Datasheet](https://www.nvidia.com/en-us/data-center/h100/)
- [NVIDIA A100 Datasheet](https://www.nvidia.com/en-us/data-center/a100/)
- [NVIDIA A10 Datasheet](https://www.nvidia.com/en-us/data-center/products/a10-gpu/)

---

## License

MIT License - Feel free to use and share.
