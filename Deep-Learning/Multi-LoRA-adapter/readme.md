# Multi‑LoRA Adapters in vLLM: Switching, Performance, and When You Really Need Chat Templates

## TL;DR

- vLLM supports multiple LoRA adapters loaded and resident in memory, switchable per request with ≈0 delay via `LoRARequest` (offline) or `--lora-modules` (server).
- Chat Template is **not required** for adapter switching; its value is in keeping the prompt format consistent with each adapter’s fine-tuning data, improving output quality and maintainability.
- LoRA adapters are resource-efficient for small/mid LLMs with fixed domain tasks; RAG suits larger LLMs needing real-time knowledge retrieval.

---

## Background & Problem
In extending an LLM's ability with external capabilities or domain knowledge, common approaches include:
1. **Fine-tuning / LoRA adapters** — efficient, adjusts a small set of parameters.
2. **Function calling** — integrate tool APIs.
3. **RAG (Retrieval-Augmented Generation)** — external up-to-date knowledge retrieval.

**Problems addressed:**
- Naïve handling: Switching LoRA for different tasks → unload current adapter, load new one → multi-second delay.
- In multi-task/multi-user environments, we need adapters resident in memory and selected per request with almost zero switch delay.
- Models fine-tuned with specific prompt formats degrade when given mismatched prompts during inference.

---

## Method — Fully Reproducible Steps

### 1. Install vLLM and HuggingFace Hub
```bash
pip install vllm huggingface_hub
```



### 2. Prepare Base Model & Adapters

Two example base models:

- `Qwen/Qwen3-4B-Base` (Benjamin’s example)
- `meta-llama/Meta-Llama-3-8B` (Your example)

Adapters:

- Translation: English→French, English→Japanese
- Task-specific: OASST assistant, xLAM tool invocation

Download adapters:

```
huggingface-cli download kaitchup/Meta-Llama-3-8B-oasst-Adapter --local-dir ./oasst_adapter
huggingface-cli download kaitchup/Meta-Llama-3-8B-xLAM-Adapter --local-dir ./xlam_adapter
```



------

### 3. [Optional] Prepare Jinja Chat Template

Only needed if you want prompts to match fine-tuning format exactly.
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

# Initialize base model
llm = LLM(model="Qwen/Qwen3-4B-Base", enable_lora=True, max_lora_rank=32, max_model_len=2048)

# Load adapters
oasst_path = snapshot_download("kaitchup/Meta-Llama-3-8B-oasst-Adapter")
oasstLR = LoRARequest("oasst", 1, oasst_path)

xlam_path = snapshot_download("kaitchup/Meta-Llama-3-8B-xLAM-Adapter")
xlamLR = LoRARequest("xlam", 2, xlam_path)

fr_adapter_path = "/workspace/SFT-OPUS-en-fr/checkpoint-15469"
enja_adapter_path = "/workspace/SFT-OPUS-en-ja/checkpoint-15469"
adapter_enfr = LoRARequest("enfr", 3, fr_adapter_path)
adapter_enja = LoRARequest("enja", 4, enja_adapter_path)

# Optional: load Chat Template
try:
    with open("/workspace/chat_template_translator.jinja", "r", encoding="utf-8") as f:
        CHAT_TEMPLATE = f.read()
except FileNotFoundError:
    CHAT_TEMPLATE = None

sampling_params = SamplingParams(temperature=0.8, top_p=0.95, max_tokens=512)

# Simple benchmark function
def benchmark_adapter(adapter_req, prompts, use_chat_template=False):
    print(f"\nAdapter: {adapter_req.adapter_name}")
    start_t = time.time()
    if use_chat_template and CHAT_TEMPLATE:
        outputs = llm.chat(prompts, sampling_params, lora_request=adapter_req, chat_template=CHAT_TEMPLATE)
    else:
        outputs = llm.generate(prompts, sampling_params, lora_request=adapter_req)
    end_t = time.time()
    total_time = end_t - start_t
    tokens_total = sum(o.outputs[0].token_count for o in outputs)
    tokens_sec = tokens_total / total_time if total_time > 0 else 0
    ttft = min(o.outputs[0].first_token_time for o in outputs)
    print(f"Tokens/sec: {tokens_sec:.2f}, TTFT: {ttft:.3f}s")
    if torch.cuda.is_available():
        print(f"GPU mem: {torch.cuda.memory_allocated()/1024/1024:.2f} MB")

# Run with/without Chat Template
benchmark_adapter(oasstLR, [
    "### Human: Check if the numbers 8 and 1233 are powers of two.### Assistant:",
], use_chat_template=False)

benchmark_adapter(adapter_enfr, [
    [ {"role": "system", "content": "You are a professional translator translating English to French."},
      {"role": "user", "content": "I'm an English teacher."}]
], use_chat_template=True)
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



Query via OpenAI client:

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

-  Match `max_lora_rank` to highest adapter rank to avoid VRAM waste.
-  Keep safetensors limited to LoRA A/B matrices only.
-  Use Chat Template if multiple adapters have different training prompt formats.
-  Monitor tokens/sec & TTFT per adapter pre-production.
-  In small-scale/prototype, prompt can be hardcoded instead of templates.

------

## Deployment Runbook

**Env**:

- GPU VRAM ≥ base + sum(adapter delta params)
- Python ≥3.9
- vLLM latest release

**Steps**:

1. Download base + adapters.
2. (Optional) Save Chat Template file for consistent formatting.
3. Serve with `--lora-modules`.
4. Query with matching `model` adapter name.

------

## Risks & Troubleshooting

| Issue              | Cause                  | Fix                                                  |
| ------------------ | ---------------------- | ---------------------------------------------------- |
| OOM                | VRAM insufficient      | Reduce adapters or quantize base                     |
| Poor output        | Prompt format mismatch | Use same template as fine-tuning or replicate format |
| Wrong adapter used | Model name mismatch    | Ensure IDs match `--lora-modules` registration       |
| Wasted VRAM        | max_lora_rank too high | Set exactly to highest adapter rank                  |

------

## Conclusion & Next Steps

1. Benchmark each adapter with provided script and fill performance table.
2. Decide whether to use templates based on adapter diversity and maintenance needs.
3. Deploy with monitoring and fallback logic.

------

## About Chat Template — Addressing Your Concern

**Key understanding:**

- Multi-LoRA adapter switching **does not require** Chat Template. You can use `llm.generate(..., lora_request=AdapterX)` or `vllm serve --lora-modules` without it.
- Chat Template’s value lies in:
  1. Guaranteeing input format matches fine-tuning training format → preserves output quality.
  2. In multi-adapter scenario, mapping adapter ID to its specific format without code duplication.
  3. Maintainability: hot-update prompt formats without redeploying code.

**Single adapter:** Template mainly reduces hardcoding, easier maintenance.
**Multi adapter:** Template becomes central to correct format-to-adapter mapping and preventing quality drop across tasks.

**Bottom line:**
If adapters share the same prompt structure, you can skip Chat Template. If they differ significantly, templates are a safe engineering practice to preserve quality and consistency.