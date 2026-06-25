# Attribution

This repo is a public engineering guide built around public model, dataset, framework, and Azure references.

| Item | Source |
|---|---|
| Qwen3-ASR 1.7B | https://huggingface.co/Qwen/Qwen3-ASR-1.7B |
| Qwen3-ASR GitHub repository | https://github.com/QwenLM/Qwen3-ASR |
| Qwen3-ASR official fine-tuning | https://github.com/QwenLM/Qwen3-ASR/tree/main/finetuning |
| Gemma 3n E2B-it | https://huggingface.co/google/gemma-3n-E2B-it |
| Gemma3n Transformers documentation | https://huggingface.co/docs/transformers/main/en/model_doc/gemma3n |
| FLEURS dataset | https://huggingface.co/datasets/google/fleurs |
| vLLM supported models | https://docs.vllm.ai/en/latest/models/supported_models/ |
| vLLM speech-to-text API | https://docs.vllm.ai/en/latest/api/vllm/entrypoints/speech_to_text/ |
| SGLang | https://docs.sglang.io/ |
| TensorRT-LLM multimodal support | https://nvidia.github.io/TensorRT-LLM/features/multi-modality.html |
| Hugging Face Accelerate | https://huggingface.co/docs/accelerate/index |
| Hugging Face Transformers | https://huggingface.co/docs/transformers/index |
| Hugging Face TRL | https://huggingface.co/docs/trl/index |
| Azure GPU VM sizes | https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/ |
| Azure Retail Prices API | https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices |

## Public Assets

- `data/eval-manifest.example.json` is a synthetic/public manifest template.
- `data/sample-audio/` contains public or placeholder sample-audio references only.
- `images/solution_architecture.png` and `images/validation_gates.png` are generated architecture/validation diagrams for this repo.

No customer audio, transcripts, endpoints, subscription IDs, VM IPs, tokens, or private logs should be committed to this public repo.
