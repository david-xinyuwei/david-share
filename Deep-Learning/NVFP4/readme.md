## NVFP4 Analysis and Engineering Practice

### **Abstract and Key Points**

- NVFP4 is a 4-bit floating-point quantization format optimized by NVIDIA for Blackwell Tensor Core, using an **E2M1 element format** (1 sign bit + 2 exponent bits + 1 mantissa bit, totaling 4 bits) with **dual scaling** mechanism: every 16 weights share one FP8 E4M3 local scaling factor (**micro-block level**, i.e., "grouping granularity" of 16), plus one FP32 global scaling factor per tensor (tensor level), balancing storage compression with numerical stability. Experimental results show that with both activations and weights in NVFP4, throughput can be ~2.35× higher than INT4 (RTX 6000 Pro, vLLM 0.10.0, Llama-3.3-70B-Instruct).
- **Quantization Error Advantage**: NVFP4's E4M3 fractional scaling achieves significantly lower quantization error (MSE ≈ 0.08) compared to MXFP4's E8M0 power-of-two scaling (MSE ≈ 0.72), representing a **9× error reduction**. This is because E4M3 finds an optimal scale factor that minimizes collective block errors, while E8M0 must snap to nearest 2^n values.
- **Memory and Energy Efficiency**: NVFP4 reduces memory footprint by approximately **3.5× vs FP16** and **1.8× vs FP8**. Blackwell delivers up to **25× energy efficiency** improvement over H100, while Blackwell Ultra achieves **50× improvement**, with total storage overhead of ~4.5 bits/value.
- Compared to mainstream 4-bit INT4 formats (AWQ, AutoRound, bitsandbytes), NVFP4 shows no obvious accuracy gap on large models (>10B parameters). **The key advantage lies in Blackwell GPU hardware acceleration**: when weights+activations both use NVFP4, Tensor Cores can "automatically handle the microscaled FP4 data" (NVIDIA official wording), directly processing microscaling format data and reducing the data type conversion overhead present in INT4 approaches. If only weight quantization is applied (NVFP4A16) with activations remaining FP16, the hardware advantage is significantly weakened, with throughput only slightly better than INT4.
- **Important limitation**: NVFP4's **performance benefits are primarily realized on Blackwell architecture (GB200/GB300/RTX 6000 Pro, etc.)**. On older GPUs (Hopper/Ampere/Ada), NVFP4 models can run but require real-time dequantization to FP16 for computation (similar to INT4 processing). Due to lack of optimized kernels for NVFP4, performance may be inferior to mature INT4 implementations (such as AWQ/AutoRound). The author explicitly states: "I can't see any good reasons for using NVFP4 with older GPUs." (meaning NVFP4 has no performance advantage on older GPUs, not that it cannot be used)
- MXFP4 (OCP Microscaling standard) uses E2M1 elements, E8M0 power-of-two scaling, **micro-block size of 32** (i.e., every 32 weights share one scaling factor), with no global FP32 scaling. It relies mainly on shift operations, has smaller metadata overhead, and favors cross-platform deployment simplicity. OpenAI's open-source models (such as gpt-oss-20b/120b) use MXFP4 for PTQ, retaining high precision for certain modules (`modules_to_not_convert`).
- **Accuracy Preservation**: Testing on DeepSeek-R1-0528 across 7 benchmarks shows ≤1% accuracy degradation from FP8 to NVFP4. Notably, on AIME 2024, NVFP4 (91%) even outperforms FP8 (89%) by 2%. Other benchmarks: MMLU-PRO (85%→84%), GPQA Diamond (81%→80%), Math-500 (98%→98%), demonstrating excellent accuracy preservation.
- **Selection recommendation**:
  - ✅ **With Blackwell GPU**: Prioritize NVFP4 (weights+activations), achieving 2.35× throughput improvement, 25-50× energy efficiency gains
  - ⚠️ **Older GPUs (H100/A100/RTX 40/30 series)**: NVFP4 models can run, but **performance advantage is not obvious**. Recommend using mature INT4 (AWQ/AutoRound) or MXFP4. If only for saving VRAM (4-bit storage), NVFP4 is still effective, but speed won't be faster than INT4
  - ⚠️ **Small models (<10B)**: Accuracy and performance differences lack empirical data; recommend actual evaluation before decision

### **1. Background: Why NVFP4?**

As LLM parameter counts climb, even pure inference is constrained by VRAM bandwidth and capacity. 4-bit quantization is one of the most cost-effective paths today, but traditional INT4 faces two practical bottlenecks:

- **Dequantization overhead is difficult to eliminate completely:** Even with aggressive engineering optimizations (such as vLLM, SGLang, TensorRT-LLM's kernel fusion, pipeline parallelism, etc.), weights often still need to be restored to 16-bit (or higher) at the operator entry point to utilize general-purpose tensor cores for main computation.
- **Range vs. fidelity trade-off:** INT4 often uses larger groups (such as 128) to share scaling factors, which can reduce metadata but when encountering highly heterogeneous distributions or outliers, small values are more easily lost or compressed, requiring more sophisticated grouping strategies and calibration.

NVFP4's proposal is centered on "storing and computing in 4-bit while minimizing dequantization and precision loss as much as possible," and through hardware native support, translating this design into actually measurable throughput performance improvements.

### **2. Core Design of NVFP4**

**1. Element Format and Value Range**

- Element format: FP4 E2M1 (1 sign bit, 2 exponent bits, 1 mantissa bit)
- Value range per element: approximately -6 to +6 (limited magnitude coverage)
- 4-bit alone is insufficient to cover real LLM tensor distributions, hence NVFP4 introduces "dual scaling."

**2. Dual Scaling Mechanism**

- **Micro-block scaling (block-level)**
  - Granularity: 16 elements per block (block size = 16)
  - Scaling factor type: FP8 E4M3
  - Key point: E4M3 allows fractional (non-power-of-two) scaling, enabling fine-grained adaptation to local tensor magnitudes without being dominated by outliers.

- **Global scaling (tensor-level)**
  - Each tensor has one high-precision FP32 scale to absorb long-tail range and cross-layer variance, ensuring each micro-block's FP8 scale operates in an appropriate range.

**Reconstruction formula:** x ≈ xq × s_block(FP8 E4M3) × s_tensor(FP32)

**Key insights:**
- Smaller blocks (16 vs. MXFP4's 32) mean finer-grained local adaptation, reducing outlier "drag" on the group.
- FP8 E4M3 is more flexible than power-of-two scaling, reducing systematic quantization bias. **Quantification: E4M3 achieves MSE ≈ 0.08 vs E8M0's MSE ≈ 0.72, a 9× error reduction**.
- Global FP32 scaling acts as a safety net, ensuring stability across layers and tensors with varying magnitudes.

**Why E4M3 is "better on average":**
- **E8M0** = Snaps the scale factor to nearest 2^n, which can create large quantization error for the block maximum (amax) and often leads to larger overall quantization errors.
- **E4M3** = Finds one scale factor that minimizes collective block errors—often improving accuracy for the block maximum (amax). While some individual values might be slightly less accurate, the block as a whole retains higher fidelity.

**3. Complete Comparison: FP4 / MXFP4 / NVFP4**

| Feature | FP4 (E2M1) | MXFP4 | NVFP4 |
|---------|------------|-------|-------|
| **Format Structure** | 4-bit (1 sign, 2 exponent, 1 mantissa) with software scaling factor | 4-bit (1 sign, 2 exponent, 1 mantissa), 1 shared power-of-two scale per 32-value block | 4-bit (1 sign, 2 exponent, 1 mantissa) with 1 shared FP8 scale per 16-value block |
| **Hardware Acceleration** | No | Yes | Yes |
| **Memory** | ~25% of FP16 | ~25% of FP16 | ~28.5% of FP16 (3.5× compression) |
| **Accuracy** | Risk of significant accuracy degradation vs FP8 | Risk of significant accuracy degradation vs FP8 | Reduced risk of accuracy degradation, especially for larger models |

### **3. NVFP4 and Blackwell Architecture Innovation**

#### Official NVIDIA Statement

According to NVIDIA's Blackwell white paper and developer blog:

> "NVIDIA Blackwell fifth-generation Tensor Core architecture implements NVFP4 and can **automatically handle the microscaled FP4 data** including the grouping of elements, dynamic scaling, and 4-bit matrix operations."

> Source: [Introducing NVFP4 for Efficient and Accurate Low-Precision Inference](https://developer.nvidia.com/blog/introducing-nvfp4-for-efficient-and-accurate-low-precision-inference/)

**Key terminology interpretation**:
- **"implements NVFP4"** → Tensor Core hardware has built-in NVFP4 support
- **"automatically handle"** → Automatically processes microscaling data (including grouping, dynamic scaling)
- **"4-bit matrix operations"** → Directly executes 4-bit matrix operations

**Content not explicitly stated by official sources**:
- Whether it is completely "dequantization-free" (zero-dequantization)
- Specific hardware data flow path design
- Circuit-level implementation details of FP4×FP8 scaling

**Phenomena observed from empirical data**:

NVFP4 on Blackwell shows approximately 2.35× throughput improvement compared to INT4. Possible reasons include:
- **Hardware native support**: Tensor Cores can "automatically handle the microscaled FP4 data" (official statement), directly processing microscaling format data
- **Bandwidth advantage**: 4-bit data transfer volume is comparable to INT4, reducing the data type conversion overhead present in INT4 approaches
- **Automatic scaling processing**: Hardware automatically handles micro-block scaling without requiring additional software operations
- **Dual scaling mechanism**: FP8 micro-block scale + FP32 global scale ensures numerical stability

**Energy Efficiency Gains** (NVIDIA Official Data):
- **Blackwell vs H100**: Up to **25× energy efficiency** improvement (0.4 J/token vs 10 J/token for GPT-MoE-1.8T)
- **Blackwell Ultra vs H100**: Up to **50× energy efficiency** improvement (0.2 J/token)
- **10-year evolution**: 200,000× efficiency gain from Kepler (42,000 J/token) to Blackwell Ultra (0.2 J/token)

**About different quantization schemes** (observations based on public information):

| Scheme | Data Format | Observed Characteristics |
|--------|-------------|-------------------------|
| INT4 | Integer + scale | Mature toolchain, requires dequantization steps |
| H100 FP8 | FP8 floating-point | Hopper native support, but scale operations may require precision elevation |
| NVFP4 | FP4 floating-point + FP8 scale + FP32 scale | Blackwell optimized, high observed throughput |

The above comparisons are based on publicly available performance data and architectural feature descriptions. Specific hardware implementation details (such as whether there are dedicated fusion units, data flow path design, etc.) are not detailed in NVIDIA official documentation and await further technical disclosure.

The above comparisons are based on publicly available performance data and architectural feature descriptions. Specific hardware implementation details (such as whether there are dedicated fusion units, data flow path design, etc.) are not detailed in NVIDIA official documentation and await further technical disclosure.



### **4. Experimental Results and Engineering Significance**

**1. Accuracy**

- **NVFP4 vs. FP8:** Difference ≤1% across multiple benchmarks; some (e.g., AIME 2024) show NVFP4 slightly better, but within statistical noise → "NVFP4 ≈ FP8."
- **NVFP4 vs. INT4 (AWQ/AutoRound/bitsandbytes):** On large models (e.g., Llama 3.3), NVFP4 and high-quality INT4 methods are comparable. Sometimes INT4 is slightly better, sometimes equivalent. Smaller models (<10B) may reveal larger differences.
- **NVFP4A16 vs. NVFP4:** Even with activation quantization, NVFP4 accuracy remains close to NVFP4A16 (weights-only), thanks to dual scaling design.

**2. Storage and Throughput**

- **Average storage overhead:** ~4.5 bits/value (block=16, one FP8 scale per block + one FP32 scale per tensor), higher than typical INT4 (block=128). NVFP4 models of Llama 3.3 are ~7GB larger than INT4 equivalents.
- **Memory efficiency gains**: NVFP4 reduces memory footprint by approximately **3.5× relative to FP16** and **1.8× compared to FP8**. On NVIDIA GB300 NVL72 rack-scale system (36 Grace Blackwell Ultra Superchips), total memory budget reaches **40 TB per system**, providing significant benefits for large-scale AI inference deployments.
- **Throughput advantage:** Key conclusion is Blackwell's hardware native support for NVFP4. When both weights and activations use NVFP4, Tensor Cores can "automatically handle the microscaled FP4 data" (NVIDIA official wording), directly processing microscaling format data. Measured throughput is ~2.35× vs. INT4.
- **NVFP4A16 trade-off:** When only weights are quantized and activations remain 16-bit, data type conversion or degradation occurs during computation. NVFP4A16 throughput is only marginally faster than INT4, unable to fully leverage NVFP4's "weights+activations full 4-bit" advantage.

#### Figure 1 — Inference Throughput Comparison (RTX 6000 Pro, vLLM v0.10.0)

![images](./images/1.png)

**Chart Explanation:**

- Dark green bars (Speed Input): Input-side token generation rate (tokens/sec)
- Light blue bars (Speed Output): Output-side token generation rate (tokens/sec)
- Different entries on the left of model names represent different quantization strategies or model sources

[Note 1] Benchmark source and measurement method: This article's experiments were conducted on RTX 6000 Pro (Ada) (CUDA 12.4, NVIDIA Driver 555.xx, Python 3.10, PyTorch 2.3, vLLM 0.10.0, FlashInfer disabled). Test configuration: single request; input context length 1 token; generate 512 new tokens; 1 warmup; tokens/s = generated tokens ÷ pure generation time. These numbers represent point measurements under this specific configuration, not peak throughput across batches/concurrency. Complete scripts and log examples in `benchmarks.md`.

#### Figure 2 — Accuracy + Model Size Comparison

![images](./images/2.png)

**Chart Explanation:**

- Blue bars (Score): Unified benchmark score (covering instruction following, common sense knowledge, multilingual capabilities)
- Green numbers (Size GB): Model size on disk
- This chart focuses on "quantization accuracy preservation" and "storage footprint."

### **5. MXFP4: What It Is and Key Differences from NVFP4**

MXFP4 is the OCP (Open Compute Project) Microscaling FP4 standard with the following features:

- Element type: FP4 E2M1 (same as NVFP4)
- Micro-block size: 32 (every 32 values share one scaling metadata)
- Scaling factor: E8M0 (exponent-only, equivalent to "power-of-two scaling," implemented as efficient shifts)
- No global FP32 scaling—relies solely on micro-block-level power scaling

**Design rationale:**
- Power-of-two scaling is extremely simple (shift operations), short implementation path, large optimization space for hardware/kernels.
- Larger micro-blocks mean less scaling metadata, more storage savings.
- Better preservation of small values, good robustness against outliers (natural advantage of floating-point exponents).

**NVFP4 vs. MXFP4 Comparison:**

| Feature | NVFP4 (NVIDIA Blackwell custom) | MXFP4 (OCP Microscaling standard) |
|---------|--------------------------------|-----------------------------------|
| Element format | FP4 E2M1 (1 sign+2 exp+1 mantissa) | FP4 E2M1 (1 sign+2 exp+1 mantissa) |
| Micro-block size | 16 | 32 |
| Block scaling format | FP8 E4M3 (fractional scaling) | E8M0 (power-of-two, shift-friendly) |
| Global scaling | Yes, FP32 per tensor | No, micro-block only |
| Reconstruction formula | x ≈ xq × FP8 × FP32 | x ≈ xq × 2^k (k from E8M0) |
| Dynamic range & robustness | Dual scaling + small blocks adapt to heterogeneous distributions | Power scaling preserves small values, resistant to outliers |
| Compute cost | FP8 scaling requires multiplication (Blackwell HW accelerated) | Power scaling uses shifts, highly efficient |
| Hardware path | Blackwell Tensor Core native support | Depends on vendor kernel support |
| Dequantization needed? | No if both weights+activations are NVFP4; yes for NVFP4A16 | Yes if no native support |
| Throughput vs. INT4 | ~2.3× (Blackwell + full NVFP4) | Depends on implementation |
| Accuracy | ≈FP8, error ≤1% | Better than traditional INT4; lacks direct NVFP4 comparison data |
| Storage overhead | ~4.5 bits/value | Typically lower (block 32, power scaling has less metadata) |
| Model size | Larger than typical INT4 (e.g., Llama3.3 +7GB) | Smaller than NVFP4 (implementation-dependent) |
| Calibration requirements | Full quantization needs small calibration set; NVFP4A16 doesn't | Weight quantization needs little/no calibration; activation quantization usually needs some |
| Tools & ecosystem | llm-compressor supports quantization, vLLM supports (Blackwell) | OCP standard, llm-compressor doesn't support yet |

### **6. Engineering Workflow and Practical Implementation**

#### 0. NVFP4 Quantization Tools - Official Recommendations

**NVIDIA Official Statement** (from [Introducing NVFP4 blog post](https://developer.nvidia.com/blog/introducing-nvfp4-for-efficient-and-accurate-low-precision-inference/)):
> "If you're looking to quantize your model to NVFP4, NVIDIA **TensorRT Model Optimizer** and **LLM Compressor** both offer streamlined workflows to do so."

**Two Recommended Toolchains:**

**1. TensorRT Model Optimizer** ⭐ (NVIDIA Official Primary Tool)
- **GitHub**: https://github.com/NVIDIA/TensorRT-Model-Optimizer
- **Status**: NVIDIA officially maintained, integrated with NeMo, Megatron-LM
- **Features**: Supports PTQ, QAT, pruning, distillation, speculative decoding, sparsity
- **Pre-quantized models** available on Hugging Face:
  - [DeepSeek-R1-FP4](https://huggingface.co/nvidia/DeepSeek-R1-FP4)
  - [Llama-3.3-70B-Instruct-FP4](https://huggingface.co/nvidia/Llama-3.3-70B-Instruct-FP4)
  - [Llama-3.1-405B-Instruct-FP4](https://huggingface.co/nvidia/Llama-3.1-405B-Instruct-FP4)
  - [FLUX.1-dev-onnx](https://huggingface.co/black-forest-labs/FLUX.1-dev-onnx) (image generation)
- **Deployment**: Seamlessly exports to TensorRT-LLM, vLLM, SGLang

**2. LLM Compressor** 🔄 (Community-Driven Alternative)

llm-compressor is not a standalone "NVIDIA official repository." Its origin and positioning are as follows:

- **Open-source attribution:** Hosted under the `vllm-project/llm-compressor` GitHub organization, with the core goal of providing a unified "model compression + directly inferable" product for the **vLLM inference framework** (weight quantization, activation quantization, sparsification, structural transformation).
- **Contributor ecosystem:** Maintainers and contributors come from the vLLM community, Neural Magic (which open-sourced `compressed-tensors` and early SparseML quantization/sparsification experience), Red Hat AI, etc. Citations note "Red Hat AI and vLLM Project."
- **Design inheritance:** Many `Modifier` / `oneshot` API styles continue SparseML's engineering abstractions (such as QuantizationModifier, GPTQModifier, AWQ, etc.), but are oriented toward the inference side and vLLM native consumption.
- **File format:** Uses `compressed-tensors` (safetensors extension) to record low-bit block structures, scaling metadata, and quantization schemes (including NVFP4, FP8, INT4, etc.), making generated checkpoints directly loadable by vLLM and triggering corresponding kernel paths.
- **NVFP4 support method:** By defining FP4/NVFP4 configurations in `quant_scheme.py` (block size, scaling format, etc.) + vLLM's backend kernels; not an NVIDIA-exclusive repository, but implements open-source support for the new NVFP4 data format added to **NVIDIA Blackwell**.
- **Official/community relationship:** NVIDIA promotes the NVFP4 data type in the Blackwell ecosystem; llm-compressor provides reproducible examples on the open-source side (example script links, W4A4 & W4A16 schemes), so at the "open-source practice level" it can be considered one of the recommended toolchains for NVFP4.
- **Adaptation advantages:**
  1. Unifies multiple quantization algorithms (Simple PTQ / GPTQ / AWQ / SmoothQuant / Mixed Precision).
  2. Directly produces directories loadable by vLLM without additional conversion scripts.
  3. Supports non-uniform/layered mixed quantization (different submodules use different bit widths or algorithms).
  4. Combined with mechanisms like Sequential Onloading, suitable for large models (tens to hundreds of billions of parameters) for segmented quantization.
- **Current limitations:**
  1. NVFP4's high-performance path mainly relies on vLLM; other inference frameworks haven't perfected direct-through kernels yet.
  2. Fine-tuning/QLoRA on NVFP4 is not yet mature; dequantization or selecting INT4/MXFP4 paths is needed.
  3. Activation-only NVFP4 mode not yet provided; full-chain benefits depend on "weights+activations" both being NVFP4.

- **Quick assessment:** 
  - **For production deployment**: TensorRT Model Optimizer is the official NVIDIA-recommended tool with comprehensive support and pre-optimized models
  - **For open-source experimentation**: llm-compressor is the most direct, flexibly combinable, and deeply integrated choice with vLLM in the open-source community
  - **For cross-framework needs**: If you want cross-framework support and focus on extreme volume and universality, you can also evaluate MXFP4 + INT4 (AWQ/GPTQ) and other potential low-bit kernels that may emerge later

**Deployment Framework Support:**
- ✅ **TensorRT-LLM**: Full NVFP4 support with optimized kernels
- ✅ **vLLM**: Early NVFP4 support, rapidly improving
- 🔜 **SGLang**: Upcoming NVFP4 support
- **Export Format**: Unified Hugging Face Checkpoint for easy deployment

#### 1. Quantization Workflow

- **Quantization tool:** llm-compressor already supports NVFP4 / NVFP4A16. It is a general LLM compression library maintained by the vLLM project, integrating various low-bit and sparse algorithms; it produces model directories quickly loadable by vLLM through the `compressed-tensors` scheme. NVFP4 configuration comes from open-source implementation and interfaces with Blackwell hardware paths, aiming to boost throughput and reduce weight/activation storage with minimal accuracy sacrifice.
- **Calibration set size:** 128-512 samples typically sufficient (this document's example uses 512); theoretically, beyond 1024 shows diminishing returns.
- **Sequence length recommendation:** Not below 2048; if targeting long-context inference, longer is recommended, but quantization cost increases significantly—balance quality vs. cost.
- **Data preprocessing key points:** Consistent with model training input format (chat template), avoid duplicate bos token injection.
- **Quantization scheme selection:**
  - NVFP4: Quantize both weights+activations, trade minimal accuracy for massive throughput gain.
  - NVFP4A16: Weights-only quantization, activations kept 16-bit, usually no calibration needed, but most throughput advantage lost.

#### 2. Inference Framework

- vLLM v0.10.0 basically works.
- Two practical issues developers encountered:
  - **FlashInfer:** Default enablement causes crashes with NVFP4; temporary fix is uninstalling. Performance may improve further after future fixes.
  - **Blackwell environment vLLM installation via pip may be incomplete:** Source compilation can resolve this, successfully enabling NVFP4 inference path.
- **One-line recommendation:** For running NVFP4 on Blackwell, prepare a contingency plan for source-compiling vLLM, and watch FlashInfer version compatibility.

### **3. Old GPU Compatibility Considerations**

- 3090 (Ampere) or older architectures lack NVFP4 hardware native support.
- Can load NVFP4 quantized weights to save VRAM, but inference likely requires dequantization to higher precision (e.g., FP16 Tensor Core), negating speed advantage.
- **Conclusion:** NVFP4's performance improvement requires Blackwell hardware support; on old GPUs, main value is saving VRAM (4-bit storage), not boosting inference speed.

### **4. NVFP4 vs. INT4 (AWQ/AutoRound/bitsandbytes) Trade-offs**

- **Accuracy:** On large models (e.g., Llama 3.3), both are very close to full precision; NVFP4 not significantly better than best INT4, but no obvious disadvantage either.
- **Model size:** NVFP4 typically slightly larger (micro-block 16 + FP8 + FP32); INT4 (micro-block usually 128 + FP16/FP32 scaling) saves more storage.
- **Throughput:** On Blackwell, NVFP4 significantly faster; INT4, no matter how optimized, still has dequantization or data type conversion path resistance.
- **Ease of use:** INT4 has mature ecosystem (AWQ, AutoRound, bitsandbytes, GPTQ, etc.); NVFP4 smoother natively on Blackwell.

**Engineering Recommendations:**
- Have Blackwell and pursue extreme TPS/TTFT → prioritize NVFP4 (weights+activations)
- No Blackwell, but want VRAM compression without rewriting kernels → mature INT4 more reliable
- Cross-platform & simple deployment → MXFP4 (if dedicated kernel or framework support available) is pragmatic choice

#### Appendix: INT4 Group Quantization and Scale Selection Quick Reference

Common INT4 "group quantization" approach: every N weights share one scaling factor scale, first divide float by scale and round to 0..15 (or signed range), then multiply back (dequantize) before computation.

**Simplest example (unsigned 0..15):**

```
Weight group: [3.14159, 2.71828, 1.41421, 0.57722]
max(|w|) = 3.14159
scale = 3.14159 / 15 ≈ 0.209439 → 0.2094
Quantized integer q = round(w/scale): [15,13,7,3]
Dequantized q*scale ≈ [3.141,2.722,1.466,0.628]
```

**Key phenomenon:** Maximum value fits closely, small/medium values have larger relative error, because all weights share one scale, being "stretched."

**Common scale strategy comparison (simplified):**

| Strategy | Formula/Concept | Pros | Cons | Use Cases |
|----------|----------------|------|------|-----------|
| Max-based | max(\|w\|)/(S) | Simple, no overflow | Affected by outliers | Large models fast PTQ |
| Percentile | P99(\|w\|)/S | Low main body error | Extreme values saturate | Long tail/few outliers |
| Per-channel | Separate max/S per channel | Highest accuracy | More metadata | Small models/sensitive tasks |
| L2 optimal | min Σ(w - q*scale)^2 | Min global reconstruction error | High computation cost | Offline high-quality quantization |
| Learned Rounding (AutoRound) | Learn up/down rounding | Protects important weights | Algorithm complexity | Code/math tasks |
| Activation-aware (AWQ) | Weight channels by activation stats | Improves key channel fidelity | Needs activation stats | Small models & multilingual |

**Outlier impact quick reference:** If 127 values in [-0.8,0.8], only 1 value=5.0:
- Max-based: scale≈5.0/15≈0.333 → coarser main body precision
- Percentile(P99≈0.8): scale≈0.8/15≈0.0533 → good main body precision, 5.0 clipped to≈0.8 (saturation error)

**Simple error approximation (uniform distribution):** step size Δ = a/S, expected absolute error E[\|ε\|]≈Δ/2. Reducing a (clip/ignore outliers) or increasing S (more levels/finer granularity) both reduce error.

**Quick decision:**
- Pursue "good enough+speed": Max or Percentile grouping (128)
- Pursue "small model high fidelity": Per-channel + AWQ/AutoRound
- Obvious long tail: Percentile + activation-aware
- Offline extreme compression: L2 optimization + Learned rounding combination

This section is an engineering quick reference on quantization error and scale selection, facilitating rapid trade-offs across different models and tasks.

### 5. MXFP4 Two Loading/Computation Modes

- **Storage compression mode (dequantize=True, common in Hugging Face default LoRA fine-tuning path)**
  - Loads to GPU as BF16/FP16 full-precision tensors
  - High VRAM consumption (close to BF16), computation uses high-precision matmul
  - Suitable for LoRA/full-parameter fine-tuning (needs full-precision gradients), or offline inference with sufficient VRAM
- **Resident computation mode (dequantize=False, Ollama / vLLM-gptoss dedicated kernels)**
  - Keeps MXFP4 low-bit weights resident in GPU
  - Low VRAM usage (~1/4 of BF16), computation uses low-bit kernels/custom CUDA kernels
  - Suitable for low-VRAM scenarios for efficient deployment, edge inference, or Hopper series with optimized kernels

**Engineering insights:**
- Whether models published in MXFP4 format perform "true 4-bit inference" depends on the framework you use and the dequantize switch; incorrect loading paths will lose 4-bit VRAM and throughput advantages.
- OAI-OSS's mxfp4 PTQ scheme reflects "don't convert certain modules" engineering trade-off: keep most sensitive/critical paths at high precision, use 4-bit float for the rest, balancing compression rate and stability.

### 6. Calibration and Dataset Selection Practical Recommendations

**Basic recommendations:**
- **Sample count:** 128-512 usually sufficient; for extreme fidelity can go to 1024, but diminishing returns
- **Sequence length:** Recommend ≥2048; if business target is long-context inference (32k/128k), cover longer sequences during calibration, but computation cost increases significantly
- **Distribution matching:** Make calibration samples as close as possible to real online distribution (instruction-type, code, math, dialogue, multi-turn, etc.)
- **Model input consistency:** Maintain complete preprocessing pipeline from training (template, tokenization, special symbols), avoid extra bos token causing distribution drift

**Long-sequence calibration advanced strategy** (based on practical experience):

When targeting long-context inference (e.g., processing 16k+ token documents), adopt **mixed sampling strategy:**

```python
# Strategy 1: Use only long sequences (e.g., samples >16k tokens from open-r1/OpenR1-Math-220k)
TOKEN_THRESHOLD = 16000
ds = ds.filter(lambda ex: ex["n_tokens"] >= TOKEN_THRESHOLD)
ds = ds.shuffle(seed=42).select(range(512))

# Strategy 2: Mix long and short sequences (recommended)
# - 512 short sequences (<16k): cover common distribution
# - 512 long sequences (>16k): strengthen long-context calibration
short_samples = ds.filter(lambda ex: ex["n_tokens"] < 16000).shuffle(seed=42).select(range(512))
long_samples = ds.filter(lambda ex: ex["n_tokens"] >= 16000).shuffle(seed=43).select(range(512))
ds = concatenate_datasets([short_samples, long_samples])
```

**Notes:**
- Long-sequence calibration **computation cost significantly increases** (16k vs 2k difference ~8×)
- Not recommended to use 32k for all samples, will cause excessive quantization time
- If long-context performance still unsatisfactory, increase `TOKEN_THRESHOLD` or long-sequence sample proportion
- Reference notebook: `Quantize_LLMs_to_NVFP4_with_LLM_Compressor_Calibration_with_Long_Sequences.ipynb`

### 7. Fine-tuning and Incremental Training: NVFP4 + QLoRA Feasibility

- **In theory:** NVFP4 is a data type and format; QLoRA can work with any base model
- **In reality:** Currently common frameworks don't provide ready-made support for "QLoRA on NVFP4"; implementation difficulty is not high, but toolchain needs to be integrated
- **Recommendation:** If you need LoRA/QLoRA immediately, short-term can still choose mature INT4 or MXFP4 paths; if you're targeting Blackwell's extreme throughput, waiting for framework support for NVFP4 training/fine-tuning is a reasonable strategy

### 8. Selection Decision Tree

- Is your online inference deployed on Blackwell?
  - Yes: Prioritize NVFP4 (weights+activations). If accuracy concerns, try NVFP4 first; then downgrade to NVFP4A16 to evaluate loss vs. throughput contrast.
  - No: Do you have MXFP4 direct-through kernels or use OAI-OSS dedicated paths? If yes, prioritize MXFP4; otherwise, safely use INT4 (AWQ/AutoRound).
- Is your VRAM extremely tight but speed requirements moderate?
  - Yes: MXFP4 or INT4 (weights resident, activations high-precision) better control cost; NVFP4A16 also alternative (mainly saves VRAM).
- Is your task long-context or sensitive to preserving small values (e.g., retrieval attention, sparse gating)?
  - Yes: Prioritize solutions with finer scaling and dual scaling (NVFP4), or preserve key modules at high precision under MXFP4.

### 9. Common Questions

- **vLLM + FlashInfer:** May crash with NVFP4; temporarily uninstall or disable; watch for version fixes
- **Blackwell vLLM installation:** pip version may be incomplete; prioritize source compilation
- **NVFP4A16 expectation management:** Throughput not equal to NVFP4, only slightly faster than INT4, can't apply NVFP4 speed claims
- **Calibration sample bias:** Samples too short or distribution mismatch will cause degradation in long-context or specific capabilities
- **Module ignore strategy:** If ignore list doesn't cover truly sensitive modules, local collapse easily occurs; conversely, ignoring too much reduces compression ratio and throughput
- **Old GPUs running NVFP4:** Understand "can fit ≠ faster," don't have overly high speed expectations

### **7. Code Examples**

```bash
pip install llmcompressor datasets transformers
```

**Quantize weights + activations:**

```python
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier
from transformers import AutoTokenizer, AutoModelForCausalLM
from datasets import load_dataset

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

NUM_CALIBRATION_SAMPLES = 512
MAX_SEQUENCE_LENGTH = 2048

# Load dataset
ds = load_dataset("HuggingFaceH4/ultrachat_200k", split=f"train_sft[:{NUM_CALIBRATION_SAMPLES}]")
ds = ds.shuffle(seed=42)

# Preprocess: apply chat template
def preprocess(example):
    return {"text": tokenizer.apply_chat_template(example["messages"], tokenize=False)}
ds = ds.map(preprocess)

# Tokenize (careful with bos tokens - chat_template already added it)
def tokenize(sample):
    return tokenizer(sample["text"], padding=False, max_length=MAX_SEQUENCE_LENGTH, 
                    truncation=True, add_special_tokens=False)
ds = ds.map(tokenize, remove_columns=ds.column_names)

# Configure quantization
recipe = QuantizationModifier(targets="Linear", scheme="NVFP4", ignore=["lm_head"])

# Apply quantization
oneshot(
    model=model,
    dataset=ds,
    recipe=recipe,
    max_seq_length=MAX_SEQUENCE_LENGTH,
    num_calibration_samples=NUM_CALIBRATION_SAMPLES,
)

# Save compressed model
SAVE_DIR = MODEL_ID.rstrip("/").split("/")[-1] + "-NVFP4"
model.save_pretrained(SAVE_DIR, save_compressed=True)
tokenizer.save_pretrained(SAVE_DIR)
```

**Weights-only quantization (NVFP4A16):**

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"

# Load model
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

# Configure weights-only quantization
recipe = QuantizationModifier(targets="Linear", scheme="NVFP4A16", ignore=["lm_head"])

# Apply quantization (no calibration dataset needed)
oneshot(model=model, recipe=recipe)

# Save in compressed-tensors format
SAVE_DIR = MODEL_ID.rstrip("/").split("/")[-1] + "-NVFP4A16"
model.save_pretrained(SAVE_DIR, save_compressed=True)
tokenizer.save_pretrained(SAVE_DIR)
```

**Quantize LM Head:**

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"

# Load model
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

# Configure quantization including lm_head
recipe = QuantizationModifier(targets="Linear", scheme="NVFP4A16")

# Apply quantization
oneshot(model=model, recipe=recipe)

# Save to disk in compressed-tensors format
SAVE_DIR = MODEL_ID.rstrip("/").split("/")[-1] + "-NVFP4A16LMH"
model.save_pretrained(SAVE_DIR, save_compressed=True)
tokenizer.save_pretrained(SAVE_DIR)
```

### **7.1 Improved Example: Mixed Long/Short Sequence NVFP4 Calibration (Recommended Practice)**

The following example builds upon the "quick start" by adding:
1. **Sequence length statistics and bucketing:** Simultaneously covers long-context and regular instruction distributions, reducing risk of long-sequence degradation from using only short samples.
2. **Mixed sampling strategy:** Prioritize extracting specified number of long sequences (e.g., ≥16k tokens), then supplement with short sequences to reach total calibration count.
3. **Fallback logic:** If dataset has insufficient long sequences, automatically lowers threshold or fills with shorter samples without interrupting workflow.
4. **Lightweight evaluation:** Calculates proxy loss and generation throughput on small batch before/after quantization, helping quickly verify quality and performance.
5. **VRAM estimation:** Provides simple formulas to help estimate VRAM usage differences between NVFP4 and NVFP4A16.

**Use case:** Pursuing more stable long-context capabilities (chat, retrieval, multi-turn tool calling, code completion) without exponential increase in calibration cost.

```python
import math, time, torch
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"  # Replace with your model
NUM_CALIBRATION_SAMPLES = 1024          # Total calibration sample target
LONG_TARGET = 512                       # Desired long sequence sample count
LONG_TOKEN_THRESHOLD = 16000            # Long sequence determination threshold (adjustable 12k~24k)
SHORT_MIN_LENGTH = 2048                 # Minimum retention length
MAX_SEQUENCE_LENGTH = 32000             # Unified truncation limit (balance VRAM)
SEED = 42

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=True)
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto")

ds = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft[:5000]")
ds = ds.shuffle(seed=SEED)

# 1. Apply original chat template, maintaining consistency with training format
def apply_template(example):
    return {"text": tokenizer.apply_chat_template(example["messages"], tokenize=False)}
ds = ds.map(apply_template)

# 2. Rough tokenization to count token length (no duplicate special tokens)
def length_only(example):
    ids = tokenizer(example["text"], add_special_tokens=False)["input_ids"]
    return {"token_length": len(ids)}
ds = ds.map(length_only)

# 3. Bucket filtering for long/short samples
long_ds = ds.filter(lambda x: x["token_length"] >= LONG_TOKEN_THRESHOLD)
short_ds = ds.filter(lambda x: SHORT_MIN_LENGTH <= x["token_length"] < LONG_TOKEN_THRESHOLD)

actual_long = min(LONG_TARGET, len(long_ds))
needed_short = NUM_CALIBRATION_SAMPLES - actual_long

# Fallback: if insufficient long sequences, print warning; if short also insufficient, fall back to any samples
if actual_long < LONG_TARGET:
    print(f"[Fallback] Only obtained {actual_long} long sequences (<{LONG_TARGET}). Will supplement with more short sequences.")
if len(short_ds) < needed_short:
    print(f"[Fallback] Insufficient short sequences {needed_short}, current {len(short_ds)}. Using other samples to fill.")
    remaining = needed_short - len(short_ds)
    extra_pool = ds.filter(lambda x: x["token_length"] < SHORT_MIN_LENGTH)
    extra_take = min(remaining, len(extra_pool))
    short_ds = short_ds.select(range(len(short_ds)))
    extra_ds = extra_pool.select(range(extra_take))
    from datasets import concatenate_datasets
    short_ds = concatenate_datasets([short_ds, extra_ds])

calib_long = long_ds.select(range(actual_long))
calib_short = short_ds.select(range(min(needed_short, len(short_ds))))

from datasets import concatenate_datasets
calib_ds = concatenate_datasets([calib_long, calib_short]).shuffle(seed=SEED)
print("Calibration set composition: long", len(calib_long), "short", len(calib_short), "total", len(calib_ds))

# 4. Real tokenization + truncation (avoid duplicate bos addition)
def tokenize(example):
    return tokenizer(example["text"], add_special_tokens=False, truncation=True, max_length=MAX_SEQUENCE_LENGTH)
token_cols = [c for c in calib_ds.column_names if c not in ("text", "token_length")]
calib_ds = calib_ds.map(tokenize, remove_columns=token_cols)

# 5. Configure NVFP4 (weights+activations), ignore lm_head to reduce precision risk
recipe = QuantizationModifier(targets="Linear", scheme="NVFP4", ignore=["lm_head"])

oneshot(
    model=model,
    dataset=calib_ds,
    recipe=recipe,
    max_seq_length=MAX_SEQUENCE_LENGTH,
    num_calibration_samples=len(calib_ds),
)

# 6. Lightweight evaluation: generation throughput + proxy loss
def quick_loss(batch_size=4):
    subset = calib_ds.select(range(batch_size))
    total, count = 0.0, 0
    for sample in subset:
        ids = torch.tensor([sample["input_ids"]], device=model.device)
        out = model(input_ids=ids, labels=ids)
        total += out.loss.item()
        count += 1
    return total / max(count, 1)

def gen_speed(prompt="Hello", steps=64, warmup=1):
    for _ in range(warmup):
        _ = model.generate(tokenizer(prompt, return_tensors="pt").input_ids.to(model.device), max_new_tokens=8)
    start = time.time()
    _ = model.generate(tokenizer(prompt, return_tensors="pt").input_ids.to(model.device), max_new_tokens=steps)
    t = time.time() - start
    return steps / t

loss_proxy = quick_loss()
tokens_per_sec = gen_speed()
print(f"[Eval] Proxy Loss: {loss_proxy:.3f} | Gen Speed: {tokens_per_sec:.1f} tok/s")

# 7. Save compressed weights (directly compatible with vLLM)
SAVE_DIR = MODEL_ID.split("/")[-1] + "-NVFP4-mixed-calib"
model.save_pretrained(SAVE_DIR, save_compressed=True)
tokenizer.save_pretrained(SAVE_DIR)
print("Saved ->", SAVE_DIR)

# 8. VRAM estimation hint (approximate):
# NVFP4 average ~4.5 bits/param; NVFP4A16 ~4 bits/param (weights only);
# FP16 ~16 bits/param. Can estimate GB using param_count * bits/8/1024**3.
param_count = sum(p.numel() for p in model.parameters())
nvfp4_gb = param_count * 4.5 / 8 / 1024**3
fp16_gb = param_count * 16 / 8 / 1024**3
print(f"Param Count: {param_count/1e9:.2f}B | NVFP4≈{nvfp4_gb:.2f}GB | FP16≈{fp16_gb:.2f}GB (weight portion approximate)")
```

> **Usage recommendation:** If long-context performance remains low subsequently, increase `LONG_TOKEN_THRESHOLD` or total calibration sample count; if VRAM is tight, try NVFP4A16 first then evaluate throughput vs. quality difference.

#### Additional FAQ (Related to Toolchain)

**Q: Can llm-compressor quantized models only be inferred with vLLM?**  
A: No. Full NVFP4 performance improvement requires **Blackwell GPU + vLLM (or other frameworks supporting NVFP4)**; other frameworks may dequantize on loading, losing hardware acceleration advantage. NVFP4A16 (weights-only) is easier to use across frameworks but also loses most performance advantage.

**Q: Is llm-compressor NVIDIA's officially recommended quantization tool for NVFP4?**  
A: The repository README provides NVFP4 / NVFP4A16 examples and configurations (W4A4/W4A16), representing the most direct official support path for NVFP4 in current open-source ecosystem, can be considered "officially supported implementation."

**Q: Can I quantize only activations without quantizing weights (Activation-only NVFP4)?**  
A: Current toolchain doesn't provide this mode; NVFP4's core advantage comes from weights+activations both being low-bit to trigger hardware direct-through, otherwise performance gain is extremely low.

**Q: What if I need LoRA/QLoRA fine-tuning?**  
A: Currently recommend dequantizing back to FP16/BF16 or using mature INT4/MXFP4 training paths; incremental training support on NVFP4 is still being refined in the ecosystem.

### **8. Conclusion**

If you have Blackwell GPU, NVFP4 is a worthy 4-bit quantization approach to prioritize: achieve inference throughput far exceeding INT4 with minimal accuracy sacrifice, through hardware native support and robust numerical characteristics from dual scaling (micro-block FP8 + global FP32).

If your environment is cross-platform or lacks Blackwell, MXFP4 is a mature and pragmatic engineering solution, especially with reusable PTQ configuration patterns demonstrated in OAI-OSS implementations (preserving critical modules at high precision, using 4-bit float for the rest). Looking ahead, NVFP4 ecosystem will likely continue maturing (including fine-tuning paths and sampling kernel fixes), while MXFP4 standardization and multi-vendor optimization will accelerate. These two routes may coexist long-term: one for "hardware-specialized throughput extremes," another for "ecosystem universality and deployment simplicity."

---

## **9. References and Sources**

### NVIDIA Official Resources
- **Blackwell Architecture White Paper**: [NVIDIA Blackwell Platform Overview](https://www.nvidia.com/en-us/data-center/technologies/blackwell-architecture/)
- **NVFP4 Developer Blog**: [NVIDIA Developer Blog - FP4 Quantization](https://developer.nvidia.com/blog/)

### Open-Source Tools and Implementations
- **llm-compressor**: [vllm-project/llm-compressor](https://github.com/vllm-project/llm-compressor) - NVFP4/NVFP4A16 quantization tool
- **vLLM Inference Framework**: [vllm-project/vllm](https://github.com/vllm-project/vllm) - Supports NVFP4 on Blackwell
- **compressed-tensors**: [neuralmagic/compressed-tensors](https://github.com/neuralmagic/compressed-tensors) - NVFP4 weight storage format

### Industry Standards and Specifications
- **OCP MXFP4 Standard**: [Open Compute Project - Microscaling Formats](https://www.opencompute.org/documents/ocp-microscaling-formats-mx-v1-0-spec-final-pdf)
- **OpenAI gpt-oss Implementation**: [openai/gpt-oss](https://github.com/openai/gpt-oss) - MXFP4 PTQ reference implementation

### INT4 Quantization Methods Comparison
- **AWQ**: [mit-han-lab/llm-awq](https://github.com/mit-han-lab/llm-awq) - Activation-Aware Weight Quantization
- **AutoRound**: [intel/auto-round](https://github.com/intel/auto-round) - Learned rounding optimization
- **GPTQ**: [IST-DASLab/gptq](https://github.com/IST-DASLab/gptq) - Classic INT4 quantization
- **bitsandbytes**: [TimDettmers/bitsandbytes](https://github.com/TimDettmers/bitsandbytes) - 4-bit quantization library

### Evaluation Benchmarks
- **Test Environment**: RTX 6000 Pro (Ada), CUDA 12.4, vLLM 0.10.0, Llama-3.3-70B-Instruct
- **Reproduction Method**: See `benchmarks.md` for complete scripts and configurations
- **Test Protocol**: Single request, input 1 token, generate 512 tokens, 1 warmup, FlashInfer disabled
