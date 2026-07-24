# Evidence and Reproducibility

## Evidence Chain

Every published MI300X score follows this chain:

1. evaluator result artifact;
2. strict private coverage/configuration validator;
3. evidence SHA-256 manifest;
4. atomic completion marker;
5. public hash-only response audit;
6. repository validator and immutable Git commit.

Interrupted chunks without a marker are excluded, even if a progress bar showed completed requests.

## Public Audit Schema

Each line in `data/raw-audit/<dataset>.jsonl` contains:

- `question_id`, `repeat_id` or an explicit provenance limitation;
- binary `metric`;
- finish/token metadata when available;
- SHA-256 hashes for prompt, ground truth, prediction, response, and response ID;
- the source artifact index.

The text itself is omitted to avoid redistributing benchmark prompts, answer keys, or model generations.

## Provenance Limitations

- AIME has explicit repeat IDs.
- CMMLU repeat 0 is inferred from a validated legacy one-repeat canary; repeats 1–2 are explicit.
- MMLU-Redux has explicit repeat IDs.
- SuperGPQA has one repeat by contract; the legacy one-response rows are labeled inferred.
- MinervaMath preserves three ordered response slots per question, but the legacy artifact does not expose explicit repeat IDs.
- MMLU-Pro proves two configured repeats and the aggregate result, but per-repeat attribution is unavailable in the legacy artifact.

These limitations do not prevent recomputing the published aggregate subset scores; they do prevent stronger per-repeat claims.

## Recalculate

```bash
python scripts/validate_repo.py .
```

The command validates:

- six dataset entries;
- full-contract totals of 60,533 questions and 134,239 responses;
- snapshot totals of 3,216 observed questions and 8,080 validated responses;
- audit file hashes, row counts, binary metrics, unique audit keys, and accuracy;
- README/CN values against the machine-readable source.

## Evaluator Source Boundary

Complete supplied evaluator files are not redistributed because a public redistribution license was not established. `patches/` contains exact unified diffs and original/patched SHA-256 values. `scripts/prepare_mini_eval_smoke.py` is the patching tool used to apply the controls.
