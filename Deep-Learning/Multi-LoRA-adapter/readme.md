# Multi‑LoRA Adapters in vLLM: Switching, Performance, and When You Really Need Chat Templates


## Running on Azure

This project can be deployed on **Azure Virtual Machines** with GPU support.

| Item | Details |
|---|---|
| **Azure VMs** | [GPU-optimized VM sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/overview) |
| **Compute** | Select VM size based on model requirements |


## TL;DR

- vLLM supports multiple LoRA adapters loaded and resident in memory, switchable per request with ≈0 delay via `LoRARequest` (offline) or `--lora-modules` (server).
- Chat Template is **not required** for adapter switching; its value is in keeping the prompt format consistent with each adapter’s fine-tuning data, improving output quality and maintainability.
- LoRA adapters are resource‑efficient for small/mid LLMs with fixed domain tasks; RAG suits larger LLMs needing real-time knowledge retrieval.

------

## Background & Problem

When extending an LLM's abilities with external capabilities or domain knowledge, common approaches include:

1. **Fine‑tuning / LoRA adapters** — efficient, adjusts a small set of parameters.
2. **Function calling** — integrate tool APIs.
3. **RAG (Retrieval‑Augmented Generation)** — retrieves and uses up‑to‑date external knowledge.

**Problems addressed:**

- Naïve handling: switching LoRA for different tasks → unload current adapter, load new one → multi‑second delay.
- In multi‑task/multi‑user environments, we need adapters resident in memory and selected per request with near‑zero switch delay.
- Models fine‑tuned with specific prompt formats degrade when given mismatched prompts during inference.

------

## Method — Fully Reproducible Steps

### 1. Install vLLM and HuggingFace Hub

```
pip install vllm huggingface_hub
```



------

### 2. Prepare Base Model & Adapters

Two example base models:

- `Qwen/Qwen3-4B-Base`
- `meta-llama/Meta-Llama-3-8B`

Adapters:

- Translation: English→French, English→Japanese
- Task‑specific: OASST assistant, xLAM tool invocation

Download adapters:

```
huggingface-cli download kaitchup/Meta-Llama-3-8B-oasst-Adapter --local-dir ./oasst_adapter
huggingface-cli download kaitchup/Meta-Llama-3-8B-xLAM-Adapter --local-dir ./xlam_adapter
```



------

### 3. [Optional] Prepare Jinja Chat Template

Only needed if you want prompts to match fine‑tuning format exactly.
Example: `/workspace/chat_template_translator.jinja`

```
{# Messages: list of {role, content} #}
{%- macro text_of(m) -%}
  {%- if m.content is string -%}{{ m.content | trim }}
  {%- else -%}{{ m.content | selectattr("type","equalto","text") | map(attribute="text") | join("\n") | trim }}
  {%- endif -%}
{%- endmacro -%}

{%- set sys = (messages | selectattr("role","equalto","system") | map(attribute="content") | list | first) -%}
{%- if sys %}<start>{{ sys | trim }}{% endif -%}

{%- for m in messages if m.role != "system" -%}
  {%- if m.role == "user" -%}<user>{{ text_of(m) }}
  {%- elif m.role in ["assistant","translator"] -%}<translator>{{ text_of(m) }}
  {%- endif -%}
{%- endfor -%}

{%- if add_generation_prompt %}<translator>{% endif -%}
```



------

### 4. Offline Multi-LoRA Invocation

```
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest
from huggingface_hub import snapshot_download
import time
import torch

llm = LLM(model="Qwen/Qwen3-4B-Base", enable_lora=True, max_lora_rank=32, max_model_len=2048)

oasst_path = snapshot_download("kaitchup/Meta-Llama-3-8B-oasst-Adapter")
oasstLR = LoRARequest("oasst", 1, oasst_path)

xlam_path = snapshot_download("kaitchup/Meta-Llama-3-8B-xLAM-Adapter")
xlamLR = LoRARequest("xlam", 2, xlam_path)

fr_adapter_path = "/workspace/SFT-OPUS-en-fr/checkpoint-15469"
enja_adapter_path = "/workspace/SFT-OPUS-en-ja/checkpoint-15469"
adapter_enfr = LoRARequest("enfr", 3, fr_adapter_path)
adapter_enja = LoRARequest("enja", 4, enja_adapter_path)

try:
    with open("/workspace/chat_template_translator.jinja", "r", encoding="utf-8") as f:
        CHAT_TEMPLATE = f.read()
except FileNotFoundError:
    CHAT_TEMPLATE = None

sampling_params = SamplingParams(temperature=0.8, top_p=0.95, max_tokens=512)

def benchmark_adapter(adapter_req, prompts, use_chat_template=False):
    print(f"\nAdapter: {adapter_req.adapter_name}")
    start_t = time.monotonic()
    if use_chat_template and CHAT_TEMPLATE:
        outputs = llm.chat(prompts, sampling_params, lora_request=adapter_req, chat_template=CHAT_TEMPLATE)
    else:
        outputs = llm.generate(prompts, sampling_params, lora_request=adapter_req)
    end_t = time.monotonic()
    total_time = end_t - start_t
    total_tokens = sum(len(o.outputs[0].token_ids) for o in outputs if o.outputs and hasattr(o.outputs[0], "token_ids"))
    tokens_sec = total_tokens / total_time if total_time > 0 else 0
    ttft = None
    gpu_mem = torch.cuda.memory_allocated()/1024/1024 if torch.cuda.is_available() else None
    print(f"Tokens/sec: {tokens_sec:.2f}, TTFT: {ttft}, Time: {total_time:.3f}s, GPU Mem: {gpu_mem} MB")

benchmark_adapter(oasstLR, ["### Human: Check if the numbers 8 and 1233 are powers of two.### Assistant:"], use_chat_template=False)
benchmark_adapter(adapter_enfr, [[{"role": "system", "content": "You are a professional translator translating English to French."}, {"role": "user", "content": "I'm an English teacher."}]], use_chat_template=True)
```



------

### 5. Online Serve with Multiple Adapters

```
vllm serve Qwen/Qwen3-4B-Base \
  --enable-lora \
  --max-lora-rank 32 \
  --lora-modules oasst=./oasst_adapter \
                 xlam=./xlam_adapter \
                 enfr=/workspace/SFT-OPUS-en-fr/checkpoint-15469 \
                 enja=/workspace/SFT-OPUS-en-ja/checkpoint-15469
```



OpenAI client query:

```
from openai import OpenAI
client = OpenAI(api_key="EMPTY", base_url="http://localhost:8000/v1")
completion = client.chat.completions.create(
    model="enfr",
    messages=[
        {"role": "system", "content": "You are a professional translator translating English to French."},
        {"role": "user", "content": "I'm an English teacher."}
    ]
)
print(completion)
```

------

## Engineering Recommendations

- Match `max_lora_rank` to highest adapter rank to avoid VRAM waste.
- Keep safetensors limited to LoRA A/B matrices only.
- Use Chat Template if multiple adapters have different training prompt formats.
- Monitor tokens/sec & TTFT per adapter before production.
- For prototypes with few adapters, hardcode prompt formats.
- Optimize server flags: `--gpu-memory-utilization`, `--tensor-parallel-size`, `--max-num-batched-tokens`.
- Multi-tenant safe: bind adapter names to tenant permissions.
- Observability: integrate Prometheus/Grafana with vLLM metrics.
- Gradual rollout: new adapters get low-traffic test before full release.

------

## Deployment Runbook

**Env**:

- GPU VRAM ≥ base model + sum(adapter delta params)
- Python ≥3.9
- vLLM latest release

**Steps**:

1. Download base + adapters.
2. Optional: save Chat Template file.
3. Serve with `--lora-modules`.
4. Query with matching `model` adapter name.

**Example QLoRA Offline**:

```
llm = LLM(model="Qwen/Qwen3-4B-Base", quantization="bitsandbytes", qlora_adapter_name_or_path="/path/to/qlora_adapter", enable_lora=True, max_lora_rank=32)
```



**Example QLoRA Serve**:

```
vllm serve Qwen/Qwen3-4B-Base --quantization bitsandbytes --load-format bitsandbytes --qlora-adapter-name-or-path /path/to/qlora_adapter --enable-lora --max-lora-rank 32
```



------

## Risks & Troubleshooting

| Issue                      | Cause                           | Fix                                    |
| -------------------------- | ------------------------------- | -------------------------------------- |
| OOM                        | VRAM insufficient               | Reduce adapters / quantize base        |
| Poor output                | Prompt format mismatch          | Match training format                  |
| Wrong adapter used         | Model name mismatch             | Ensure IDs match registration          |
| Wasted VRAM                | max_lora_rank too high          | Set to highest adapter rank            |
| Unsupported adapter format | Contains full modules           | Use LoRA A/B matrices only             |
| Dimension mismatch         | Adapter not matching base model | Re-export from compatible base version |

------

## Conclusion & Next Steps

1. Benchmark each adapter and fill the table.
2. Decide on template usage based on format diversity and ROI.
3. Deploy with monitor/fallback mechanisms.

------

## About Chat Template

- Multi‑LoRA adapter switching **does not require** Chat Template.
- It helps:
  1. Ensure prompt format matches fine‑tuning data.
  2. Map adapter IDs to specific formats without duplicating code.
  3. Allow prompt format hot‑update without redeploying.

Single adapter: reduces hardcoding.
Multi‑adapter: essential for correct adapter‑format mapping and quality stability.

------

### Chat Template Decision Tree

```
             +-------------------------------+
             |  Are all adapters using the    |
             |  same prompt format structure? |
             +-----------------------+-------+
                                     |
                  YES                |              NO
       +---------------------+       |       +------------------+
       | Is the number of     |       |       | Do prompt formats |
       | adapters <= 2 ?      |       |       | differ heavily or |
       +----------+----------+       |       | are tasks highly  |
                  |                  |       | format-sensitive? |
       YES        |       NO         |       +---------+---------+
   +--------------+----+  +----------+----+            |      
   | Hardcode prompt   |  | Template optional, |    YES |    NO
   | format in code.   |  | for easier future  |  +-----+----+   
   |                   |  | maintenance.      |  | Use Chat |   
   | (No Template)     |  | (Weigh ROI)        |  | Template |   
   +-------------------+  +-------------------+  +----------+   
                                                    |     
                                               (Format diff, high
                                                maintainability gain)
```





