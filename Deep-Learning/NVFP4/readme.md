## NVFP4 Analysis and Engineering Practice

### **Abstract and Key Points**

- NVFP4 is a 4-bit floating-point quantization format optimized by NVIDIA for Blackwell Tensor Core, using an E2M1 element format with dual scaling (micro-block FP8 E4M3 + global FP32). This design significantly boosts inference throughput while maintaining near-lossless accuracy. The first paper’s conclusion shows that with both activations and weights in NVFP4, throughput can be ~2.35× higher than INT4.
- Compared to mainstream 4-bit INT4 formats (AWQ, AutoRound, bitsandbytes), NVFP4 shows no obvious accuracy gap on large models but benefits from Blackwell’s “full direct pass without dequantization” advantage. If only weight quantization is applied (NVFP4A16), most throughput gains are lost.
- MXFP4 (OCP Microscaling standard) also uses E2M1 elements but adopts E8M0 power scaling, a micro-block size of 32, and no global FP32 scaling. It relies mainly on shift operations, has smaller metadata overhead, and favors simplicity and cross-platform deployment. In the second paper, OpenAI’s gpt-oss-20b/120b use MXFP4 for PTQ, retaining high precision for certain modules (`modules_to_not_convert`).
- Selection recommendation: On Blackwell, prioritize NVFP4 (weights + activations). Cross-platform or non-Blackwell environments may choose MXFP4 (OAI-OSS) to run stably with low VRAM, although speed advantages depend largely on matched low-bit kernels and hardware paths.

### **1. Background: Why NVFP4?**

As LLM parameter counts climb, even pure inference is constrained by VRAM bandwidth and capacity. 4-bit quantization is one of the most cost-effective paths today, but traditional INT4 faces two practical bottlenecks:

- **Dequantization overhead:** Even with aggressive engineering optimizations (kernel fusion, pipeline parallel, etc.), weights are often restored to 16-bit or higher before main tensor core computation.
- **Range vs. fidelity trade-off:** INT4 often shares scaling factors over large groups (e.g., 128 values), reducing metadata but risking loss of small values in heterogeneous distributions unless carefully grouped and calibrated.

NVFP4 aims to store and compute in 4-bit while minimizing dequantization and accuracy loss, with hardware-native support turning this into observable throughput gains.

### **2. Core Design of NVFP4**

1. **Element format:** FP4 E2M1 (1 sign bit, 2 exponent bits, 1 mantissa bit)
   Range per value: ~-6 to +6 — insufficient to cover real tensor distributions inside LLMs without scaling.

2. **Dual Scaling:**

   - **Micro-block scaling:**
     - Block size: 16 elements
     - Scaling factor type: FP8 E4M3 — supports fractional scaling close to local tensor magnitude.
   - **Global scaling:**
     - One FP32 scale per tensor — absorbs long-tail variance and cross-layer differences.

   Reconstruction formula: `x ≈ xq × s_block(FP8 E4M3) × s_tensor(FP32)`

Key points: Smaller blocks (16 vs. MXFP4’s 32), flexible FP8 scaling, and the global FP32 scale allow NVFP4 to adapt well to heterogeneous value distributions and outliers.

### **3. Experimental Results and Engineering Significance**

**Accuracy:**

- NVFP4 ≈ FP8 (≤1% diff).
- NVFP4 ≈ INT4 methods on large models (sometimes slightly better or worse depending on case).
- NVFP4A16 (weights-only) has similar accuracy to full NVFP4 thanks to dual scaling.

**Storage & Throughput:**

- Storage ~4.5 bits/value; NVFP4 models can be ~7 GB larger than INT4 equivalents.
- On Blackwell: NVFP4 weights+activations run directly on Tensor Core without dequantization, boosting throughput by ~2.35× vs. INT4.
- NVFP4A16 loses most of this throughput benefit.

*(Charts and detailed figure explanations omitted here for brevity in README)*

### **4. MXFP4 Overview and Differences from NVFP4**

MXFP4 (OCP Microscaling FP4) features:

- FP4 E2M1 elements, block size 32, scaling via E8M0 power-of-two (shift-friendly).
- No global FP32 scaling — simpler and lighter metadata, better cross-platform potential.
- Less flexible scaling than NVFP4, but simpler compute path.
- Throughput depends on kernel support (e.g., vLLM/Ollama-specific paths).
- Generally smaller model size than NVFP4.

| Feature              | NVFP4 (NVIDIA Blackwell-optimized)       | MXFP4 (OCP standard)          |
| -------------------- | ---------------------------------------- | ----------------------------- |
| Element Format       | FP4 E2M1                                 | FP4 E2M1                      |
| Block Size           | 16                                       | 32                            |
| Block Scaling Format | FP8 E4M3 (fractional scaling)            | E8M0 (power-of-two scaling)   |
| Global Scaling       | Yes, FP32 per tensor                     | No                            |
| Formula              | x ≈ xq × FP8 × FP32                      | x ≈ xq × 2^k                  |
| Compute Cost         | FP8 multiply (Blackwell HW acceleration) | Shift operations              |
| HW Path              | Blackwell Tensor Core native pass        | Kernel-dependent              |
| Storage Overhead     | More (smaller block size, extra scales)  | Less                          |
| Typical Use          | Max throughput on Blackwell              | Cross-platform simplification |

### **5. Engineering Workflow**

**Quantization Tools:**
`llm-compressor` supports NVFP4. Calibration set size: 128–512 samples recommended. Sequence length: ≥2048 tokens. Preprocessing must match training format.

**Inference Framework:**
vLLM v0.10.0 works with NVFP4; source build recommended on Blackwell. Disable FlashInfer if unstable.

**Old GPU Compatibility:**
No native NVFP4 path — can load NVFP4 weights to save VRAM but will likely require runtime dequantization.

**NVFP4 vs. INT4:**

- Accuracy: similar on large models.
- Model size: NVFP4 slightly larger.
- Throughput: NVFP4 faster only on Blackwell with activations also in NVFP4.
- Ecosystem: INT4 more mature; NVFP4 smoother natively on Blackwell.

### **6. Example Code**

```
pip install llmcompressor datasets transformers
```



**Quantize weights + activations:**

```
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier
from transformers import AutoTokenizer, AutoModelForCausalLM
from datasets import load_dataset
import torch

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

NUM_CALIBRATION_SAMPLES = 512
MAX_SEQUENCE_LENGTH = 2048
ds = load_dataset("HuggingFaceH4/ultrachat_200k", split=f"train_sft[:{NUM_CALIBRATION_SAMPLES}]").shuffle(seed=42)

def preprocess(example):
    return {"text": tokenizer.apply_chat_template(example["messages"], tokenize=False)}
ds = ds.map(preprocess)

def tokenize(sample):
    return tokenizer(sample["text"], padding=False, max_length=MAX_SEQUENCE_LENGTH, truncation=True, add_special_tokens=False)
ds = ds.map(tokenize, remove_columns=ds.column_names)

recipe = QuantizationModifier(targets="Linear", scheme="NVFP4", ignore=["lm_head"])

oneshot(
    model=model,
    dataset=ds,
    recipe=recipe,
    max_seq_length=MAX_SEQUENCE_LENGTH,
    num_calibration_samples=NUM_CALIBRATION_SAMPLES,
)

SAVE_DIR = MODEL_ID.split("/")[-1] + "-NVFP4"
model.save_pretrained(SAVE_DIR, save_compressed=True)
tokenizer.save_pretrained(SAVE_DIR)
```



**Weights-only quantization (NVFP4A16):**

```
from transformers import AutoModelForCausalLM, AutoTokenizer
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

recipe = QuantizationModifier(targets="Linear", scheme="NVFP4A16", ignore=["lm_head"])
oneshot(model=model, recipe=recipe)

SAVE_DIR = MODEL_ID.split("/")[-1] + "-NVFP4A16"
model.save_pretrained(SAVE_DIR, save_compressed=True)
tokenizer.save_pretrained(SAVE_DIR)
```



### **7. Conclusion**

If you have Blackwell GPUs, NVFP4 is the preferred 4-bit format for maximum throughput with minimal accuracy loss, thanks to hardware-native dual scaling and full 4-bit path for both weights and activations.
If cross-platform or without Blackwell, MXFP4 offers a practical, standardized approach for low VRAM use, especially with OAI-OSS PTQ workflows.