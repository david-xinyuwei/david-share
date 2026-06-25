# Gemma 3n Audio/ASR Feasibility Report

Generated: 2026-06-25
Source: HuggingFace model card + Transformers Gemma3n docs + H100 route attempt

## Key Finding

**Gemma 3n (E2B/E4B) officially supports audio input including ASR, but this repo does not yet report Gemma FLEURS CER.**

In this validation run, Gemma 3n E2B-it was made accessible, the 10.9 GB model was downloaded, and a clean Python environment was prepared. The system Python environment hit a PyTorch SDPA/cuDNN frontend failure before a valid audio CER measurement could be collected. A clean venv with PyTorch 2.6.0+cu124 and cuDNN 9.1.0 was created, but the final official text/audio smoke JSON was not collected before SSH timeout. This is an engineering route status, not an ASR-quality result.

## Evidence

| Attribute | Value | Source |
|---|---|---|
| HuggingFace tags | `automatic-speech-recognition`, `automatic-speech-translation`, `audio-text-to-text` | [Model card](https://huggingface.co/google/gemma-3n-E4B-it) |
| Architecture class | `Gemma3nForConditionalGeneration` | HuggingFace transformers |
| Audio encoding | 6.25 tokens per second, single channel | Model card |
| Training audio data | "diverse set of sound samples enables the model to recognize speech, transcribe text" | Model card - Training Dataset |
| Safety eval | "audio-to-text" explicitly tested | Model card - Ethics |
| Intended use | "Audio Data Extraction: Transcribe spoken language, translate speech to text" | Model card - Usage |
| Languages | 140+ spoken languages trained | Model card |
| vLLM support | ✅ `Gemma3nForConditionalGeneration` listed in vLLM supported models | [vLLM docs](https://docs.vllm.ai/en/latest/models/supported_models/) |
| SGLang support | ✅ Listed on HuggingFace local-app links | [HuggingFace model page](https://huggingface.co/google/gemma-3n-E4B-it?local-app=sglang) |

## H100 Route Status (2026-06-25)

| Check | Result | Evidence |
|---|---|---|
| License access | Accepted by operator before download | HuggingFace gated access was unlocked |
| Model download | Completed to `/root/gemma-3n-E2B-it`; observed size ~11 GB; 3 safetensors shards | `results/gemma3n_h100_route_status.json` |
| Official model class | `Gemma3nForConditionalGeneration` | [HF model card](https://huggingface.co/google/gemma-3n-E2B-it), [Transformers docs](https://huggingface.co/docs/transformers/main/en/model_doc/gemma3n) |
| System Python smoke | Model loads, then text-only generation fails in PyTorch SDPA/cuDNN frontend | `results/gemma3n_h100_route_status.json` |
| Clean environment | `/root/gemma3n_env` created with PyTorch 2.6.0+cu124 and cuDNN 9.1.0 | `results/gemma3n_h100_route_status.json` |
| Final CER | Not available | No valid Gemma ASR transcript/CER was collected |

### Correct Official API Shape

Use the official class and processor path first. Do not infer Gemma 3n usage from Qwen3-ASR or other multimodal models.

```python
from transformers import AutoProcessor, Gemma3nForConditionalGeneration
import torch

model = Gemma3nForConditionalGeneration.from_pretrained(
	"google/gemma-3n-E2B-it",
	device_map="auto",
	attn_implementation="sdpa",
	torch_dtype=torch.bfloat16,
).eval()
processor = AutoProcessor.from_pretrained("google/gemma-3n-E2B-it", padding_side="left")

messages = [
	{"role": "user", "content": [{"type": "text", "text": "Say hello in Chinese."}]}
]
inputs = processor.apply_chat_template(
	messages,
	tokenize=True,
	return_dict=True,
	return_tensors="pt",
	add_generation_prompt=True,
).to(model.device)
```

### Why the Failed Attempt Still Matters

The failed run is not a quality result, but it is useful for engineering triage:

- Qwen3-ASR ran in the same broader H100 workflow with a dedicated package and vLLM transcription endpoint.
- Gemma 3n requires a stricter Transformers/PyTorch/cuDNN stack and should be validated in a clean environment before any customer-facing CER or latency claim.
- For customer discussion, Gemma should be framed as a candidate multimodal backbone, not as a drop-in replacement for Qwen3-ASR until this route passes text-only smoke, audio smoke, and FLEURS/customer CER.

## Model Sizes

| Model | Effective Params | Total Params | Memory Footprint |
|---|---|---|---|
| gemma-3n-E2B-it | 2B effective | ~5B total | ~2B active (with PLE caching + param skipping) |
| gemma-3n-E4B-it | 4B effective | ~8B total | ~4B active |

## Architecture Innovations (Relevant for Customer)

1. **MatFormer**: Nested sub-models within larger model → can run smaller core for simple tasks
2. **PLE Caching**: Per-layer embeddings cached to fast storage → reduces runtime memory
3. **Conditional Parameter Loading**: Audio/vision params loaded on-demand → text-only tasks skip them
4. **MobileNet-V5 encoder**: Vision encoder optimized for on-device

## ASR-Specific Capabilities

- **Input**: Audio encoded at 6.25 tokens/second from single channel
- **Tasks**: Speech recognition, speech translation, audio analysis
- **Context**: 32K tokens total (audio + text)
- **Fine-tuning**: QLoRA supported via HuggingFace Transformers ([official guide](https://ai.google.dev/gemma/docs/core/huggingface_text_finetune_qlora))

## Comparison with Qwen3-ASR for a Customer-Owned ASR Stack

| Dimension | Qwen3-ASR | Gemma 3n |
|---|---|---|
| Primary purpose | Dedicated ASR model | General multimodal (text+image+audio+video) |
| ASR architecture | Custom audio encoder + CTC + LM decoder | General transformer with audio tokenizer |
| Sizes available | 0.6B, 1.7B | E2B (~2B), E4B (~4B) |
| vLLM serving | ✅ Dedicated transcription endpoint | ✅ General multimodal endpoint |
| SGLang serving | ❌ Not confirmed | ✅ Confirmed |
| TRT-LLM | ❌ | ❌ (not in matrix yet) |
| Chinese ASR quality | Optimized (CER ~7% on FLEURS) | Unknown for Chinese ASR specifically |
| Fine-tuning | Official SFT script | QLoRA via HuggingFace |
| On-device deployment | Not optimized | Specifically designed for phones/laptops/tablets |

## Recommendation

```
"Gemma 3n is a viable ASR backbone if customer needs:
- On-device/edge deployment (phones, tablets)
- Multimodal capability (audio + vision in same model)
- SGLang serving (not available for Qwen3-ASR)

However, for pure Chinese ASR quality:
- Qwen3-ASR is purpose-built and likely has better CER
- Gemma 3n's Chinese ASR performance is unvalidated

Onsite question: 'Are you using Gemma for ASR specifically, or for multimodal
tasks where audio is one input modality?'"
```

## Validation TODO (if customer confirms Gemma use)
- [ ] Run official text-only smoke in `/root/gemma3n_env` and save JSON evidence
- [ ] Run Gemma 3n audio smoke using the official `Gemma3nForConditionalGeneration` + `processor.apply_chat_template()` route
- [ ] Run Gemma 3n on FLEURS `cmn_hans_cn` and compare CER with Qwen3-ASR
- [ ] Test vLLM/SGLang serving only after local transformers route passes
- [ ] Profile inference speed comparison on H100
