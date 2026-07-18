# Exact 64K/1K Fixed-Acceptance Evidence

This sanitized evidence pack supports the single-node TP8, fixed-BS16 Decode result. It contains two fresh-service optimized repetitions and their two same-image no-CK baselines.

## Measurement Identity

- Input: exactly 65,536 server-accounted tokens per request
- Requested output: 1,024 server-accounted tokens per request
- Batch: 16
- Repetitions: two fresh services per variant
- Speculative Decode: `SGLANG_SIMULATE_ACC_LEN=3`, `match-expected`
- Role: fixed-acceptance performance benchmark; not natural-acceptance or output-quality validation

`Total generated tokens (retokenized)` is the length obtained by tokenizing the returned `generated_text` again. It is not the number of accepted draft tokens. The large difference between server-accounted output tokens (16,384) and retokenized generated-text tokens (4,112) is preserved explicitly as a method boundary.

## Files

| File | Purpose |
|---|---|
| `optimized-rep*.client.txt` | Sanitized client summaries, including generated and retokenized output accounting |
| `optimized-rep*.scheduler.txt` | Full-batch scheduler windows used by the transition guard |
| `baseline-rep*.client.txt` | Same-image no-CK client summaries |
| `baseline-rep*.scheduler.txt` | Same-image no-CK full-batch scheduler windows |
| `optimized-kernel-marker.txt` | Sanitized evidence that the CK bpreshuffle module loaded |
| `SHA256SUMS.txt` | Integrity manifest for this evidence pack |

Run `python3 scripts/analyze_exact64_evidence.py` from a fresh clone. The analyzer verifies this manifest, recomputes all four run means, applies the predeclared transition guard, checks output accounting, and compares its result with `data/validation/decode-fixed-batch-audit.json`.

The original full logs remain privately archived. Their SHA-256 values are recorded in `data/validation/decode-fixed-batch-audit.json`; this public pack contains only the minimum sanitized windows needed to recompute the reported statistic. It supports independent recomputation and consistency checking of the disclosed windows, not independent proof of the provenance or completeness of the privately archived full logs.