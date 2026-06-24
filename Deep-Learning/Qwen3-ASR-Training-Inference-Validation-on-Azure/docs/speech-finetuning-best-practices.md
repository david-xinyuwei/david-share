# Speech Fine-Tuning Best Practices

This checklist distills the audio SFT engineering pattern from [`../../Multimodal-Models/SFT-Phi-4-mm/readme.md`](../../Multimodal-Models/SFT-Phi-4-mm/readme.md) and adapts it for Qwen/Gemma-style ASR validation.

The Phi-4-mm reference is a speech-translation fine-tuning project, not a Qwen3-ASR benchmark. Use it for training mechanics: data contract, label masking, audio-aware collation, distributed evaluation, and before/after scoring.

## 1. Start With the Task Contract

| Task | Input | Label | Primary metric |
|---|---|---|---|
| ASR | audio + instruction | original-language transcript | WER / CER / hotword recall |
| Speech translation | audio + instruction | translated text | BLEU / chrF plus manual spot checks |
| Audio LLM correction | transcript/audio + instruction | corrected transcript or structured text | WER/CER delta and hallucination check |
| Meeting pipeline | chunks + speaker context | stitched transcript with speaker/time metadata | WER/CER + DER + timestamp error |

Do not train on text-only pairs if the target product must consume audio. The sample must preserve the audio frontend input.

## 2. Audio Sample Shape

The Phi-4-mm SFT path builds each sample around:

- an audio array
- a sampling rate
- a task instruction
- a target answer
- model-specific audio embeddings and audio sizes after processor conversion

For ASR, the analogous sample is:

```text
User content: <audio_token> + "Transcribe the audio in the original language. Return only the transcript."
Assistant label: <ground-truth transcript><eos>
```

For speech translation, the label is the translated text. For a customer ASR PoC, keep the task contract fixed across all runs.

## 3. Label Masking

A reliable audio SFT setup should train only the assistant answer span.

| Segment | Label behavior |
|---|---|
| System prompt | ignore index, usually `-100` |
| User instruction | ignore index |
| Audio placeholder / audio embeddings | ignore index |
| Assistant answer | supervised target tokens |
| EOS / answer suffix | included if the model expects it |

This is the same principle used in the Phi-4-mm reference: the prompt side is masked and the target answer span is trained.

## 4. Audio-Aware Collator

Plain text padding is not enough. The collator must preserve audio-related tensors.

| Tensor / field | Why it matters |
|---|---|
| `input_ids` | text prompt and answer tokens |
| `labels` | masked prompt + supervised answer |
| `attention_mask` | text attention |
| `input_audio_embeds` or model-specific audio tensor | actual audio representation |
| `audio_embed_sizes` | tells the model where audio embeddings begin/end |
| `audio_attention_mask` | prevents padding audio frames from being treated as signal |
| `input_mode` / modality flag when required | selects speech mode in multimodal models |

If a custom model uses different names, document the mapping before training.

## 5. Fine-Tuning Method Selection

| Situation | Suggested first method | Escalation |
|---|---|---|
| Domain vocabulary misses | small LoRA/domain SFT or hotword correction | larger domain dataset |
| Output formatting drift | prompt-supervised SFT | schema/decoder-specific adapter |
| Long audio failures | pipeline fix first | model fine-tune only after chunking is stable |
| Memory pressure | QLoRA/adapters | larger GPU or BF16 LoRA |
| Dedicated ASR route with official training recipe | official recipe | custom adapter only after baseline |
| Audio LLM route | prompt-supervised audio SFT | full SFT after adapter baseline |

Do not change data generation, label normalization, model method, and quantization in the same experiment.

## 6. Training Configuration Guardrails

| Area | Best practice |
|---|---|
| Precision | Use BF16 where hardware supports it; use FP16 only when validated |
| FlashAttention | Enable only with compatible GPU, dtype, and package versions |
| Batch size | Ensure global batch is divisible by GPUs × per-device batch |
| Gradient accumulation | Use it to stabilize effective batch without increasing per-device memory |
| Gradient checkpointing | Useful for memory; record `use_reentrant` behavior because versions differ |
| Dataloader | Tune workers, prefetch, pin memory; ASR often bottlenecks on decode |
| Distributed eval | Gather all predictions and labels before scoring |
| Checkpointing | Test save and reload before trusting final metrics |

## 7. Evaluation Before and After Training

Every fine-tune should produce before/after artifacts.

| Artifact | Required |
|---|---|
| `eval_before.json` | model outputs and labels before training |
| `eval_after.json` | model outputs and labels after training |
| metric summary | WER/CER/hotword for ASR; BLEU/chrF for translation |
| hard sample list | examples that worsened or still fail |
| environment facts | torch, transformers, accelerate, peft, CUDA, GPU, driver |

Loss curves are useful, but they are not the acceptance metric for ASR.

## 8. Phi-4-mm Lessons to Carry Forward

| Lesson | Carry-forward rule |
|---|---|
| Audio encoder SFT must keep audio tensors in the batch | Do not reduce audio SFT to text-only training |
| `model.set_lora_adapter('speech')` selects the speech adapter route in Phi-4-mm | For other models, identify the equivalent model-supported adapter route |
| `ANSWER_SUFFIX` / stop tokens matter | Use model-native stop tokens to prevent over-generation |
| Evaluation must decode generated tokens only after the prompt span | Avoid measuring copied prompt text as model output |
| BLEU was appropriate for speech translation | For ASR, use WER/CER/hotword instead |
| Package versions were pinned | Pin multimodal/audio dependencies; do not rely on floating latest versions |

## 9. Customer PoC Acceptance Criteria

A speech fine-tuning run is ready to discuss with a customer only when it has:

```text
[ ] exact model checkpoint and license
[ ] frozen train/eval split
[ ] audio-aware data contract
[ ] label masking verified
[ ] before-training metric
[ ] after-training metric
[ ] saved generated outputs and labels
[ ] environment/version record
[ ] hard-sample analysis
[ ] serving regression after fine-tune
```

If any item is missing, call it an experiment, not a recommendation.
