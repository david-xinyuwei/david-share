# Sanitized Evidence

The files under `sanitized-runs/` are public attestations derived from authenticated hosted runs. They are not synthetic fixtures and they are not raw event logs.

Raw evidence remains private because it can contain service endpoints, immutable work identifiers, environment metadata, and generated payload text. The public files retain only the assertions needed to evaluate the documented main scenario.

Run `python scripts/build_public_evidence.py` to rebuild `data/validation-matrix.json` and `evidence/manifest.json`, then run `python scripts/validate_evidence.py` to verify the contract and all hashes.

Synthetic events used for parser regression tests are isolated under `tests/fixtures/` and labeled `test-fixture` in `scenario-manifest.json`.
