# Customer Discovery Checklist

Use this checklist in the first technical meeting.

## Model Route

- Exact base checkpoint and model architecture.
- Whether the route is dedicated ASR, audio LLM, omni multimodal, Gemma audio, Whisper-style, or custom.
- Whether model code/config/tokenizer/audio frontend was modified.
- Whether timestamps and forced alignment are required.

## Evaluation Data

- Total training hours and evaluation hours.
- Languages, dialects, accents, and noise conditions.
- Human transcript availability.
- Hotword list and speaker labels.
- Data movement constraints and de-identification rules.

## Training Stack

- Launch command and config files.
- Accelerate, DeepSpeed, FSDP, TRL, transformers versions.
- Current failure type: OOM, NCCL, data loader, checkpoint, loss spike, quantization.
- GPU utilization and step time.
- Checkpoint size, save interval, and resume behavior.

## Serving Stack

- Current production endpoint and PoC endpoint.
- vLLM/SGLang/TensorRT-LLM/TensorRT/CTranslate2 version and startup command.
- Input contract and output schema.
- RTF, P50/P95, concurrency, success rate.
- Long-audio pipeline: VAD, chunk overlap, stitching, diarization, hotwords.

## Azure Constraints

- Region, timeline, and GPU count.
- Whether customer data can move to Azure.
- Current cloud baseline and cost model.
- Security/compliance constraints.

