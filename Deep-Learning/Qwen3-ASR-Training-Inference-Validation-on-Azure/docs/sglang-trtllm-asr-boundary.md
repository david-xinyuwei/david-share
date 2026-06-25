# SGLang / TensorRT-LLM ASR Support Boundary Report

Generated: 2026-06-25
Source: GitHub repos + official docs

## Summary

| Framework | Qwen3-ASR Support | Audio/ASR Category | Evidence |
|---|---|---|---|
| **vLLM** | ✅ Native | Dedicated `Transcription` category with `Qwen3ASRForConditionalGeneration` + `Qwen3ASRRealtimeGeneration` | [vLLM supported models docs](https://docs.vllm.ai/en/latest/models/supported_models/) |
| **SGLang** | ⚠️ Partial (generic multimodal) | No dedicated ASR/transcription endpoint. Supports Qwen2-Audio via generic multimodal path. Supports Gemma 3n. No `Qwen3ASRForConditionalGeneration` in model registry. | [SGLang GitHub](https://github.com/sgl-project/sglang) — model list mentions "Qwen" but not Qwen3-ASR specifically |
| **TensorRT-LLM** | ❌ Not listed | Only Whisper in ASR. Qwen support is text-only (Qwen/Qwen1.5/Qwen2/Qwen3 CausalLM). No Qwen3-ASR architecture. | [TRT-LLM support matrix](https://nvidia.github.io/TensorRT-LLM/reference/support-matrix.html) |

## SGLang Detail

### What SGLang Supports (as of v0.5.13, June 2026)
- **LLM models**: Llama, Qwen, DeepSeek, Kimi, GLM, GPT, Gemma, Mistral
- **Multimodal**: Supports audio input via generic multimodal pipeline
- **Audio-specific**: Higgs Audio v3 TTS (day-0 support blog 2026/06)
- **No dedicated ASR endpoint** like vLLM's `/v1/audio/transcriptions`

### Why Qwen3-ASR May Not Work on SGLang
1. `Qwen3ASRForConditionalGeneration` is a custom architecture (not standard `CausalLM`)
2. Requires custom processor (`Qwen3ASRProcessor`) with audio chat template
3. SGLang model registry does not list this architecture class
4. No evidence of audio transcription API endpoint in SGLang

### Workaround Possibility
- Could work if: SGLang adds Qwen3-ASR to its model registry (community PR)
- Or: Use Qwen2-Audio (different model, `Qwen2AudioForConditionalGeneration`) which may have broader multimodal support

## TensorRT-LLM Detail

### What TRT-LLM Supports for Audio/ASR
- **Whisper**: Full support (encoder-decoder architecture) — `openai/whisper-large-v3-turbo`
- **Phi-4-multimodal**: Supports audio input (`L + I + A` in PyTorch backend)
- **Qwen text models**: Qwen/Qwen1.5/Qwen2/Qwen3 for text generation only
- **Qwen-VL**: Vision-language only, no audio

### Why Qwen3-ASR Cannot Run on TRT-LLM
1. `Qwen3ASRForConditionalGeneration` is not in the support matrix
2. Architecture requires custom audio encoder + CTC decoder — not standard transformer
3. No example or community contribution for Qwen3-ASR
4. Would require writing a custom TRT-LLM model definition (significant engineering effort)

### Alternative for Customer
- If customer needs TRT-LLM for latency: use Whisper as baseline, then compare with vLLM serving Qwen3-ASR
- If customer wants to optimize Qwen3-ASR inference: vLLM is the only production-ready option currently

## Recommendation for Customer Meeting

```
"For Qwen3-ASR inference serving:
- vLLM: Production-ready, native support with dedicated transcription endpoint
- SGLang: Not confirmed for Qwen3-ASR; may work via multimodal path but untested
- TensorRT-LLM: Not supported; only Whisper for ASR

If customer uses SGLang in production for other models and wants ASR on same infra,
they should validate Qwen3-ASR compatibility themselves or use vLLM as ASR-specific
serving layer alongside SGLang for LLM workloads."
```

## Source URLs
- vLLM: https://docs.vllm.ai/en/latest/models/supported_models/
- SGLang: https://github.com/sgl-project/sglang (v0.5.13, 2026-06-11)
- TRT-LLM: https://nvidia.github.io/TensorRT-LLM/reference/support-matrix.html (v1.2.1, 2026-04-20)
