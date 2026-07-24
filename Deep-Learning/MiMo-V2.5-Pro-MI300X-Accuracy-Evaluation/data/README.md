# Data and Evidence Index

| Path | Purpose | Public boundary |
|---|---|---|
| `results-summary.json` | Canonical machine-readable snapshot | Full numeric source for README claims |
| `results-summary.tsv` | Flat six-dataset table | Same values as JSON |
| `raw-audit/*.jsonl` | Per-response metric and content hashes | No prompt, answer-key, prediction, or response text |
| `evidence/private-source-manifest.json` | Private source artifact SHA, size, and row count | Basenames and hashes only |
| `xiaomi-final-contract.json` | Final dataset/repeat/response contract | Internal paths and registry details are excluded from README claims |
| `balanced-stage-contract.json` | Interim subset contract | Retained to explain phase boundaries |

## Snapshot Totals

- Final contract: 60,533 distinct questions / 134,239 responses.
- Published MI300X evidence: 3,216 distinct questions / 8,080 responses.
- Published response coverage: 6.02%.
- Published correct responses: 7,612.

No cross-dataset aggregate accuracy is calculated. Use `python scripts/validate_repo.py .` to recompute every dataset score.
