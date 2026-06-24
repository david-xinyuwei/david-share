# vLLM ASR Support Matrix

Source: https://docs.vllm.ai/en/latest/models/supported_models/

vLLM is not a speech model. It is an inference and serving engine. It becomes relevant to speech-to-text only when the target ASR/audio model is supported by vLLM or can be integrated through a compatible model backend.

| Route | vLLM architecture | Example model | Why it matters |
|---|---|---|---|
| Qwen dedicated ASR | `Qwen3ASRForConditionalGeneration` | `Qwen/Qwen3-ASR-1.7B` | Dedicated ASR route close to the 2B-class range. |
| Qwen realtime ASR | `Qwen3ASRRealtimeGeneration` | `Qwen/Qwen3-ASR-0.6B` | Streaming / near-realtime transcription route. |
| Qwen audio LLM | `Qwen2AudioForConditionalGeneration` | `Qwen/Qwen2-Audio-7B-Instruct` | Audio understanding route; validate before using as pure long-form ASR. |
| Qwen omni | `Qwen2_5OmniThinkerForConditionalGeneration` | `Qwen/Qwen2.5-Omni-3B`, `Qwen/Qwen2.5-Omni-7B` | Multimodal route; useful only if the workload needs omni capabilities. |
| Gemma audio | `Gemma3nForConditionalGeneration` | `google/gemma-3n-E2B-it`, `google/gemma-3n-E4B-it` | Lightweight audio/multimodal route. |
| Whisper baseline | `WhisperForConditionalGeneration` | `openai/whisper-large-v3-turbo` | Common ASR baseline. |
| FunASR | `FunASRForConditionalGeneration` | `allendou/Fun-ASR-Nano-2512-vllm` | China ecosystem ASR route worth validating. |

## Red Lines

- Do not assume a customer-modified checkpoint is compatible just because the base architecture appears in the support matrix.
- Do not compare vLLM, SGLang, and TensorRT-LLM unless model checkpoint, input audio, decoding parameters, batching, and hardware are controlled.
- Do not claim WER/CER without ground-truth transcripts.
