# Numeric Claims Audit — 2026-07-24

| Claim | Public location | Source | Recalculation | Status |
|---|---|---|---|---|
| 60,533 final questions | READMEs | `data/xiaomi-final-contract.json` | Sum of six dataset sizes | PASS |
| 134,239 final responses | READMEs | `data/xiaomi-final-contract.json` | Sum of questions × repeats | PASS |
| 3,216 observed questions | READMEs | Six `data/raw-audit/*.jsonl` files | Distinct question IDs by dataset | PASS |
| 8,080 validated responses | READMEs | Six audit files | Audit row count | PASS |
| 7,612 correct responses | `data/results-summary.json` | Six audit files | Sum of binary metrics | PASS |
| Six MI300X accuracies | READMEs | Six audit files | Correct / responses | PASS |
| Six H200 references | READMEs | Provided evaluation guide | Copied as reference; not independently reproduced | SCOPED |
| 5.31% question coverage | READMEs | 3,216 / 60,533 | Script recomputation | PASS |
| 6.02% response coverage | READMEs | 8,080 / 134,239 | Script recomputation | PASS |

No overall accuracy, statistical significance, confidence interval, non-inferiority conclusion, customer acceptance, or hardware winner is claimed.
