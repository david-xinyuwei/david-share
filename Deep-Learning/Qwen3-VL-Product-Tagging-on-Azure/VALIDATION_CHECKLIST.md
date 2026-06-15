# Validation Checklist

Use this checklist before sharing the repo with a customer or publishing updates.

## Required

- Run `python scripts/validate_public_repo.py`.
- Run `python -m py_compile scripts/*.py`.
- Confirm `README.md` and `README-CN.md` have the same major sections.
- Confirm all local image links render on GitHub.
- Confirm no customer names, VM FQDNs, SSH ports, subscription IDs, private paths, or secrets appear in text files.
- Confirm sample data uses synthetic or clearly licensed public assets.

## VLM-Specific Gates

| Gate | Pass condition |
|---|---|
| Q0 image smoke | HTTP 200 plus response mentions visible image content |
| Q1 schema gate | Output parses and passes `schemas/product_tag.schema.json` |
| Q2 quality gate | Business metrics pass on customer taxonomy |
| Q3 serving gate | P50/P95/images-sec measured with production image size and prompt |
| Q4 drift gate | Hard-sample set remains stable across model, prompt, and parser changes |

## Customer Acceptance

- Replace sample taxonomy with the customer's production taxonomy.
- Re-run validation on at least 1,000 representative product images before production decisions.
- Re-check quantized checkpoints after every serving-engine or CUDA image change.
- Treat latency and F1 differences below practical noise thresholds as inconclusive without repeated runs.
