# Evaluator Modification Evidence

The supplied evaluator source is not republished wholesale because a public redistribution license was not established.

This directory provides a verifiable substitute:

- `evaluator-hashes.tsv`: dataset, original SHA-256, patched SHA-256;
- `eval_*.patch`: exact unified diff for each of the six evaluators;
- `../scripts/prepare_mini_eval_smoke.py`: patching tool used to add opt-in controls.

The patches add sample/repeat selection, provenance, response metadata, live progress, and fail-closed behavior. They do not redefine answer keys or scoring metrics.
