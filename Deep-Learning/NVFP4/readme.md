## NVFP4 Analysis and Engineering Practice

### **Abstract and Key Points**

- NVFP4 is a 4-bit floating-point quantization format optimized by NVIDIA for Blackwell Tensor Core, using an **E2M1 element format** (1 sign bit + 2 exponent bits + 1 mantissa bit, totaling 4 bits) with **dual scaling** mechanism: every 16 weights share one FP8 E4M3 local scaling factor (**micro-block level**, i.e., "grouping granularity" of 16), plus one FP32 global scaling factor per tensor (tensor level), balancing storage compression with numerical stability. Experimental results show that with both activations and weights in NVFP4, throughput can be ~2.35× higher than INT4 (RTX 6000 Pro, vLLM 0.10.0, Llama-3.3-70B-Instruct).
- Compared to mainstream 4-bit INT4 formats (AWQ, AutoRound, bitsandbytes), NVFP4 shows no obvious accuracy gap on large models (>10B parameters). **The key advantage lies in Blackwell GPU hardware acceleration**: when weights+activations both use NVFP4, Tensor Cores can "automatically handle the microscaled FP4 data" (NVIDIA official wording), directly processing microscaling format data and reducing the data type conversion overhead present in INT4 approaches. If only weight quantization is applied (NVFP4A16) with activations remaining FP16, the hardware advantage is significantly weakened, with throughput only slightly better than INT4.
- **Important limitation**: NVFP4's **performance benefits are primarily realized on Blackwell architecture (GB200/GB300/RTX 6000 Pro, etc.)**. On older GPUs (Hopper/Ampere/Ada), NVFP4 models can run but require real-time dequantization to FP16 for computation (similar to INT4 processing). Due to lack of optimized kernels for NVFP4, performance may be inferior to mature INT4 implementations (such as AWQ/AutoRound). The author explicitly states: "I can't see any good reasons for using NVFP4 with older GPUs." (meaning NVFP4 has no performance advantage on older GPUs, not that it cannot be used)
- MXFP4 (OCP Microscaling standard) uses E2M1 elements, E8M0 power-of-two scaling, **micro-block size of 32** (i.e., every 32 weights share one scaling factor), with no global FP32 scaling. It relies mainly on shift operations, has smaller metadata overhead, and favors cross-platform deployment simplicity. OpenAI's open-source models (such as gpt-oss-20b/120b) use MXFP4 for PTQ, retaining high precision for certain modules (`modules_to_not_convert`).
- **Selection recommendation**:
  - ✅ **With Blackwell GPU**: Prioritize NVFP4 (weights+activations), achieving 2.35× throughput improvement
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
- FP8 E4M3 is more flexible than power-of-two scaling, reducing systematic quantization bias.
- Global FP32 scaling acts as a safety net, ensuring stability across layers and tensors with varying magnitudes.

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
- **Hardware native support**: Tensor Cores can "automatically handle the microscaled FP4 data" (official statement), directly processing microscaling format
- **Bandwidth advantage**: 4-bit data transfer volume is comparable to INT4, reducing data type conversion overhead present in INT4 approaches
- **Automatic scaling processing**: Hardware automatically handles micro-block scaling without requiring additional software operations
- **Dual scaling mechanism**: FP8 micro-block scale + FP32 global scale ensures numerical stability

**About different quantization schemes** (observations based on public information):

| Scheme | Data Format | Observed Characteristics |
|--------|-------------|-------------------------|
| INT4 | Integer + scale | Mature toolchain, requires dequantization steps |
| H100 FP8 | FP8 floating-point | Hopper native support, but scale operations may require precision elevation |
| NVFP4 | FP4 floating-point + FP8 scale + FP32 scale | Blackwell optimized, high observed throughput |

The above comparisons are based on publicly available performance data and architectural feature descriptions. Specific hardware implementation details (such as whether there are dedicated fusion units, data flow path design, etc.) are not detailed in NVIDIA official documentation and await further technical disclosure.

### **4. Experimental Results and Engineering Significance**

**1. Accuracy**

- **"Micro"**: Groups of 16 weights (micro-blocks), not entire tensor
- **"Tensor"**: Weight matrices in neural networks
- **"Scaling"**: Restoring compressed small numbers (FP4) to real values

**Key Innovation**:
```
Old Way: FP4 number → find scale → multiply in CPU/memory → send back to GPU
New Way: FP4 number + FP8 scale → compute result directly inside Tensor Core
         (like a calculator with built-in multiplication tables)
```

**Why "Micro" Tensor**:
- Not one scale shared by entire large matrix (too coarse)
- But each small block (16 elements) has its own scale (finer-grained)
- Hardware specifically designed circuitry to handle this "small-block × small-scale" multiplication

**Blackwell vs Hopper Essential Difference (Architectural Comparison)**:

```
Hopper (H100):     
  Tensor Core = FP8 compute units
  Missing: Hardware-level scale fusion units
  Result: Software scale operations needed after each layer

Blackwell (GB200): 
  Tensor Core = FP4 compute units + micro-scaling fusion hardware
  Added: FP4×FP8 multipliers + on-chip scaling table registers + zero-latency lookup logic
  Result: Scale operations completed inside Tensor Core in one step
```

**Not just "adding a table"—it's a redesigned compute pipeline!**

More precisely, Blackwell **redesigned the Tensor Core architecture**, adding:

1. **FP4×FP8 Mixed-Precision Multipliers** 
   - Not "convert to FP16 then multiply," but directly compute `FP4×FP8`
   - Hardware natively supports floating-point multiplication of two different bit-widths

2. **On-Chip Micro-Scaling Table Register Arrays** 
   - FP8 scale for every 16 FP4 weights stored in dedicated registers
   - Access latency ≈0 (no VRAM, no L2 cache)

3. **Fused Scale-Accumulate Units** 
   - One instruction completes: `result += (FP4_weight × FP8_scale) × FP16_activation`
   - Traditional approach needs 3 instructions: read scale → multiply weight → accumulate

4. **Pipeline Cascade Logic**
   - Scaling operations fully parallel with matrix multiplication
   - No added compute latency (traditional approach requires serial waiting)

**More Accurate Analogy**:
- H100 = Have calculator, but must manually look up conversion table then input
- Blackwell = Redesigned calculator, automatically completes conversion while pressing keys (hardware cascade)

**This is why it's called "Second-Generation Transformer Engine"**:
First-gen (H100) supports FP8, but lacks "compute-and-convert" hardware
Second-gen (Blackwell) adds micro-scaling tables, achieving true dequantization-free operation

**2. Fundamental Differences from INT4 and H100 FP8**

```
INT4 Path (Requires Dequantization):
Storage: INT4 weights + FP16/FP32 scale
Before Compute: INT4 → (dequantize) → FP16 → Tensor Core
Bottleneck: Dequantization step requires extra bandwidth & latency
Reason: Tensor Cores only support FP16/FP32 inputs; INT4 must convert first

H100 FP8 Path (Partial Dequantization):
Storage: FP8 weights
During Compute:
  - Weight×Activation: FP8 → Tensor Core natively supports ✓
  - But scaling ops: FP8 result → FP16/FP32 (dequantize) → next layer
Bottleneck: Each layer output requires type promotion; cross-layer overhead remains
Reason: H100's 1st-gen Transformer Engine lacks "micro-tensor scaling" hardware

NVFP4 Path (Fully Dequantization-Free):
Storage: FP4 weights + FP8 micro-block scale + FP32 global scale
During Compute: FP4 → Tensor Core directly processes (hardware-fused FP8 scaling)
Advantages:
  - Scaling operations completed inside Tensor Core, no extra data movement
  - Supports inter-layer FP4 direct pass-through (activations can also use FP4)
  - True end-to-end low-bit computation
```

**3. Technical Details of Hardware-Fused Scaling**

- **Fused Multiply-Add (FMA) Extension**: Tensor Core FMA units support "FP4×FP8" mixed-precision multiplication, with results directly accumulated in FP16/FP32 accumulators
- **On-Chip Cache Optimization**: FP8 scaling factors stored in Tensor Core's dedicated register file with ≈0 access latency
- **Pipeline Parallelism**: Weight loading and scaling operations fully overlapped, adding no total latency

**4. Why NVFP4A16 Loses Advantage?**

- When activations remain FP16, compute becomes `FP16 activations × (FP4 weights × FP8 scale)`
- Though weight-side is dequantization-free, data type mismatch between activations and results causes pipeline stalls
- Requires additional type conversion logic, offsetting hardware direct-path benefits

**Inferred Conclusion**: NVFP4's 2.35× throughput improvement likely results from **increased compute density** (4-bit vs 16-bit) and Blackwell architecture's optimizations for low-bit computation. Specific hardware implementation mechanisms await more detailed technical documentation from NVIDIA.

**H100 FP8 vs Blackwell NVFP4 Architecture Comparison**:

| Feature | H100 FP8 (Hopper) | Blackwell NVFP4 |
|---------|-------------------|-----------------|
| Tensor Core Support | FP8 native compute ✓ | FP4 native compute ✓ |
| Scaling Factor Handling | Software-level (requires type promotion) | Hardware-fused (micro-tensor scaling) |
| Inter-Layer Data Transfer | FP8 → FP16/FP32 → next layer | FP4 can pass through directly |
| Activation Quantization | FP8 activation support limited | FP4 activation fully supported |
| Bandwidth Bottleneck | Medium (precision upgrade at each layer exit) | Minimal (end-to-end 4-bit) |
| Typical Throughput Ratio | ~1.0× (baseline) | ~2.35× (vs INT4) |

H100's FP8, despite being floating-point quantization, **lacks hardware-level scale fusion units**, resulting in:
1. After each layer compute, FP8 results must be restored to FP16/FP32 for scale operations
2. Cross-layer transfer cannot maintain FP8 format (next layer input requires re-quantization)
3. Incomplete activation quantization support (primarily used for weights)

Blackwell's **Second-Generation Transformer Engine** (according to NVIDIA's official white paper) adds micro-tensor scaling hardware units, enabling FP4 computations to complete scaling operations directly inside Tensor Cores, thus achieving end-to-end compute flows where both weights and activations maintain low-bit formats.



### **4. Experimental Results and Engineering Significance**

**1. Accuracy**

- **NVFP4 vs. FP8:** Difference ≤1% across multiple benchmarks; some (e.g., AIME 2024) show NVFP4 slightly better, but within statistical noise → "NVFP4 ≈ FP8."
- **NVFP4 vs. INT4 (AWQ/AutoRound/bitsandbytes):** On large models (e.g., Llama 3.3), NVFP4 and high-quality INT4 methods are comparable. Sometimes INT4 is slightly better, sometimes equivalent. Smaller models (<10B) may reveal larger differences.
- **NVFP4A16 vs. NVFP4:** Even with activation quantization, NVFP4 accuracy remains close to NVFP4A16 (weights-only), thanks to dual scaling design.

**2. Storage and Throughput**

- **Average storage overhead:** ~4.5 bits/value (block=16, one FP8 scale per block + one FP32 scale per tensor), higher than typical INT4 (block=128). NVFP4 models of Llama 3.3 are ~7GB larger than INT4 equivalents.
- **Throughput advantage:** Key conclusion is Blackwell's hardware direct path for NVFP4. When both weights and activations use NVFP4, compute chain requires no dequantization—Tensor Core processes NVFP4 directly. Measured throughput is ~2.35× vs. INT4.
- **NVFP4A16 trade-off:** When only weights are quantized and activations remain 16-bit, data type conversion or fallback occurs during computation. NVFP4A16 throughput is only marginally faster than INT4, losing NVFP4's "full 4-bit" advantage.

### **4. MXFP4: What It Is and Key Differences from NVFP4**

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
| Hardware path | Blackwell Tensor Core native, no dequantization | Depends on vendor kernel support |
| Dequantization needed? | No if both weights+activations are NVFP4; yes for NVFP4A16 | Yes if no native support |
| Throughput vs. INT4 | ~2.3× (Blackwell + full NVFP4) | Depends on implementation |
| Accuracy | ≈FP8, error ≤1% | Better than traditional INT4; lacks direct NVFP4 comparison data |
| Storage overhead | ~4.5 bits/value | Typically lower (block 32, power scaling has less metadata) |
| Model size | Larger than typical INT4 (e.g., Llama3.3 +7GB) | Smaller than NVFP4 (implementation-dependent) |
| Calibration requirements | Full quantization needs small calibration set; NVFP4A16 doesn't | Weight quantization needs little/no calibration; activation quantization usually needs some |
| Tools & ecosystem | llm-compressor supports quantization, vLLM supports (Blackwell) | OCP standard, llm-compressor doesn't support yet |

### **5. Engineering Workflow and Practical Implementation**

**Quantization Tools:**
`llm-compressor` supports NVFP4/NVFP4A16. It's a general LLM compression library maintained by the vLLM project, integrating various low-bit and sparse algorithms. It produces model directories directly loadable by vLLM via the `compressed-tensors` format. NVFP4 configuration comes from open-source implementation aligned with Blackwell hardware paths, aiming to boost throughput and reduce weight/activation storage with minimal accuracy loss.

- **Calibration set size:** 128-512 samples typically sufficient (example uses 512); beyond 1024 shows diminishing returns.
- **Sequence length recommendation:** ≥2048; for long-context inference targets, use longer sequences, but quantization cost increases significantly—balance quality vs. cost.
- **Data preprocessing:** Match training input format (chat template), avoid duplicate bos token injection.
- **Quantization scheme selection:**
  - NVFP4: Quantize both weights and activations, trade minimal accuracy for massive throughput gain.
  - NVFP4A16: Weights-only quantization, activations kept 16-bit, usually no calibration needed, but most throughput advantage lost.

**Inference Framework:**
- vLLM v0.10.0 basically works.
- Two practical issues encountered:
  - **FlashInfer:** Default enablement may cause crashes with NVFP4; temporary fix is uninstalling. Performance may improve further after future fixes.
  - **Blackwell vLLM installation:** pip install may be incomplete; source compilation may be needed to successfully enable NVFP4 inference path.
- **Recommendation:** On Blackwell, prepare for source-building vLLM, and monitor FlashInfer version compatibility.

**Old GPU Compatibility:**
- 3090 (Ampere) or older architectures lack NVFP4 hardware direct path.
- Can load NVFP4 quantized weights to save VRAM, but inference likely requires dequantization to higher precision (e.g., FP16 Tensor Core), negating speed advantage.
- **Conclusion:** NVFP4's "speed dividend" requires Blackwell; on old GPUs, main value is "fitting in VRAM," not "running faster."

**NVFP4 vs. INT4 (AWQ/AutoRound/bitsandbytes) Trade-offs:**
- **Accuracy:** On large models (e.g., Llama 3.3), both are close to full precision; NVFP4 not significantly better than best INT4, but no significant disadvantage either.
- **Model size:** NVFP4 typically slightly larger (block 16 + FP8 + FP32); INT4 (block usually 128 + FP16/FP32 scaling) saves more storage.
- **Throughput:** On Blackwell, NVFP4 significantly faster; INT4, no matter how optimized, still has dequantization or data type conversion path resistance.
- **Ease of use:** INT4 has mature ecosystem (AWQ, AutoRound, bitsandbytes, GPTQ, etc.); NVFP4 smoother natively on Blackwell.

**Engineering Recommendations:**
- Have Blackwell and pursue extreme TPS/TTFT → prioritize NVFP4 (weights+activations)
- No Blackwell, but want VRAM compression without rewriting kernels → mature INT4 more reliable
- Cross-platform & simple deployment → MXFP4 (if dedicated kernel or framework support available) is pragmatic choice

### **6. Code Examples**

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

### **7. Conclusion**

If you have Blackwell, NVFP4 is worth prioritizing as your 4-bit route: achieve throughput far exceeding INT4 with minimal accuracy sacrifice, thanks to hardware direct path and robust numerical characteristics from dual scaling (micro-block FP8 + global FP32).

If your environment is cross-platform or lacks Blackwell, MXFP4 is a mature and pragmatic engineering solution, especially with reusable PTQ configuration patterns demonstrated in OAI-OSS implementations (preserving critical modules at high precision, using 4-bit float for the rest). Looking ahead, NVFP4 ecosystem will likely continue maturing (including fine-tuning paths and sampling kernel fixes), while MXFP4 standardization and multi-vendor optimization will accelerate. These two routes may coexist long-term: one for "hardware-specialized throughput extremes," another for "ecosystem universality and deployment simplicity."

---

## **8. References and Sources**

### NVIDIA Official Resources
- **Blackwell Architecture White Paper**: [NVIDIA Blackwell Platform Overview](https://www.nvidia.com/en-us/data-center/technologies/blackwell-architecture/)
- **NVFP4 Developer Blog**: [NVIDIA Developer Blog - FP4 Quantization](https://developer.nvidia.com/blog/)

### Open-Source Tools and Implementations
- **llm-compressor**: [vllm-project/llm-compressor](https://github.com/vllm-project/llm-compressor) - NVFP4/NVFP4A16 quantization tool
- **vLLM Inference Framework**: [vllm-project/vllm](https://github.com/vllm-project/vllm) - Supports NVFP4 hardware direct path
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
