# Controlled 128K/192K Evidence

This sanitized evidence pack supports the MI300X-only 128K/192K selected measurements on the final AMD 7/13-derived runtime.

## Measurement Identity

- Prefill: two-node 1P1D PD, client concurrency 4, 16 prompts, OSL 1
- Decode: single-node TP8 non-PD, actual Decode batch 4, four prompts, OSL 1,024
- Inputs: 131,072 and 196,608 tokens per request
- Repetitions: one measurement run per point
- Speculative Decode: `SGLANG_SIMULATE_ACC_LEN=3`, `match-expected`
- Role: fixed-acceptance performance measurement; not natural-acceptance or output-quality validation
- H200 scope: no row-aligned 128K/192K reference is claimed

`Total generated tokens (retokenized)` is `tokenizer.encode(generated_text)` length. It is not accepted draft-token count. Decode headline throughput is the arithmetic mean over transition-guarded steady full-BS4 scheduler samples. Prefill headline throughput is aggregate input tok/s; the two surfaces are not divided or combined.

## Files

| File | Purpose |
|---|---|
| `prefill-*.client.txt` | Sanitized Prefill client summaries |
| `decode-*.client.txt` | Sanitized Decode client summaries |
| `decode-*.scheduler.txt` | Eight full-BS4 scheduler samples per Decode point |
| `optimized-kernel-marker.txt` | CK bpreshuffle module and pinned source identities |
| `SHA256SUMS.txt` | Integrity manifest |

Run `python3 scripts/analyze_controlled_isl_evidence.py` from a fresh clone. It verifies the manifest, request/token totals, metric arithmetic, fixed acceptance, the predeclared transition guard, the 128K-to-192K deltas, and consistency with the published TSV and audit JSON.

The original full logs remain privately archived. This pack independently recomputes the disclosed sanitized records and checks their consistency with the published audit; it does not independently prove private-log provenance or completeness.
