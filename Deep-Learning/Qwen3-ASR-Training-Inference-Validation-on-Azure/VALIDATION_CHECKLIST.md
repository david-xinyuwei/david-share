# Validation Checklist

Use this checklist before sharing the repo with a customer or publishing updates.

## Required

- Run `python scripts/validate_public_repo.py`.
- Run `python -m py_compile scripts/*.py`.
- Confirm `README.md` and `README-CN.md` have the same major sections.
- Confirm all local image links render on GitHub.
- Confirm no customer names, VM FQDNs, SSH ports, subscription IDs, private paths, tokens, or secrets appear in text files.
- Confirm sample data uses public or synthetic audio only.
- Confirm every headline metric in the README points to a raw JSON file under `results/`.

## ASR-Specific Gates

| Gate | Pass condition |
|---|---|
| A0 audio smoke | Public audio sample transcribes successfully and output is non-empty |
| A1 CER/WER gate | Same eval audio, same ground truth, same normalization, same metric script |
| A2 long-audio gate | 30s/60s/180s or customer-representative duration tested with RTF and output-length checks |
| A3 training stability gate | Loss, grad_norm, checkpoint/resume, and precision mode recorded |
| A4 serving gate | P50/P95/throughput/error rate measured under concurrency using the production endpoint shape |
| A5 quantization gate | Quantized model has before/after CER, not only memory or latency |

## Customer Acceptance

- Replace public FLEURS/public sample audio with representative de-identified customer audio.
- Re-run CER/WER on customer transcripts before making domain-quality claims.
- Re-check long-audio chunking, stitching, hotwords, and diarization for meeting recordings.
- Re-check serving metrics after any model, vLLM, CUDA, cuDNN, or container image change.
- Treat Gemma 3n as a candidate route until text-only smoke, audio smoke, and CER all pass in a clean environment.
