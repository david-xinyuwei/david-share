# Sanitized Evidence

The files under `sanitized-runs/` are author-attested public records derived from authenticated private hosted runs. They are not synthetic fixtures and they are not raw event logs. Public readers can validate the exact contract and committed hashes, but cannot independently replay the withheld execution.

Raw evidence remains private because it can contain service endpoints, immutable work identifiers, environment metadata, and generated payload text. The public files retain only the assertions needed to evaluate the documented main scenario.

Each record includes a commitment derived from the SHA-256 values of its retained private source artifacts. The author can use it to detect later source drift without publishing file names or contents. It is not a digital signature or public proof that the private execution occurred.

Run `python scripts/build_public_evidence.py` to rebuild `data/validation-matrix.json` and `evidence/manifest.json`, then run `python scripts/validate_evidence.py` to verify the contract and all hashes.

Synthetic events used for parser regression tests are isolated under `tests/fixtures/` and labeled `test-fixture` in `scenario-manifest.json`; committed campaign records use `sanitized-runtime-attestation`.
