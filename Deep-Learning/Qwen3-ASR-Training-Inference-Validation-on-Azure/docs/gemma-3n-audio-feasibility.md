# Gemma 3n Audio/ASR Feasibility Report

Generated: 2026-06-25
Source: HuggingFace model card + Google AI docs

## Key Finding

**Gemma 3n (E2B/E4B) officially supports audio input including ASR.**

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
- [ ] Run Gemma 3n on FLEURS zh_cn and compare CER with Qwen3-ASR
- [ ] Test vLLM serving with Gemma 3n audio transcription
- [ ] Profile inference speed comparison on H100
