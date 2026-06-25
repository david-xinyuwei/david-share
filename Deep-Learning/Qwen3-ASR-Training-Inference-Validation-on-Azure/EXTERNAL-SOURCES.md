# External Sources

| Topic | Source | Used for |
|---|---|---|
| Qwen3-ASR model card | https://huggingface.co/Qwen/Qwen3-ASR-1.7B | Official Qwen3-ASR capabilities, package usage, vLLM backend, public sample URL |
| Qwen3-ASR GitHub repo | https://github.com/QwenLM/Qwen3-ASR | Official examples and package behavior |
| Qwen3-ASR official fine-tuning | https://github.com/QwenLM/Qwen3-ASR/tree/main/finetuning | Official SFT script, JSONL format, single/multi-GPU commands |
| Phi-4 multimodal audio SFT reference | ../../Multimodal-Models/SFT-Phi-4-mm/readme.md | Internal audio SFT engineering pattern: audio-aware samples, label masking, collator, before/after evaluation |
| Phi-4 multimodal model card | https://huggingface.co/microsoft/Phi-4-multimodal-instruct | Source model referenced by the Phi-4-mm audio SFT project |
| vLLM supported models | https://docs.vllm.ai/en/latest/models/supported_models/ | ASR/transcription support matrix and Qwen3-ASR architecture rows |
| vLLM speech-to-text API | https://docs.vllm.ai/en/latest/api/vllm/entrypoints/speech_to_text/ | Serving API reference |
| SGLang docs | https://docs.sglang.io/ | Serving-engine positioning |
| TensorRT-LLM multimodal support | https://nvidia.github.io/TensorRT-LLM/features/multi-modality.html | TensorRT-LLM positioning |
| Hugging Face Accelerate | https://huggingface.co/docs/accelerate/index | Distributed training positioning |
| Hugging Face Transformers | https://huggingface.co/docs/transformers/index | Training/model ecosystem positioning |
| Hugging Face TRL | https://huggingface.co/docs/trl/index | SFT/DPO/GRPO training stack positioning |
| Whisper | https://github.com/openai/whisper | Whisper baseline reference |
| faster-whisper | https://github.com/SYSTRAN/faster-whisper | CTranslate2 Whisper baseline reference |
| WhisperX | https://github.com/m-bain/whisperX | Whisper + alignment/diarization reference |
| FunASR | https://github.com/modelscope/FunASR | China ecosystem ASR reference |
| SenseVoice | https://github.com/FunAudioLLM/SenseVoice | ASR model family reference |
| NeMo | https://github.com/NVIDIA-NeMo/NeMo | Training/ASR toolkit reference |
| Azure ND-H100-v5 | https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/ndh100v5-series | H100 VM specs and positioning |
| Gemma 3n E2B-it model card | https://huggingface.co/google/gemma-3n-E2B-it | Official Gemma 3n multimodal/audio capabilities and HF usage |
| Gemma3n Transformers docs | https://huggingface.co/docs/transformers/main/en/model_doc/gemma3n | Official `Gemma3nForConditionalGeneration`, processor, audio feature extractor, and SDPA usage |

