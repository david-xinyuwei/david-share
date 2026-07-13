# AMD Tuned Fused-MoE Expanded Concurrency Evidence

This directory is generated from the checksum-verified two-node run.
It contains all point-level client metrics, exit codes, context metadata,
DP=2 worker distributions, worker capacity summaries, and service-log gates.

The six full service logs are not published because they contain internal
addresses and runtime paths. Their SHA-256 values and deterministic gate
results are preserved in `service-validation.json`. Both rejected boundaries
and the earlier observed GPU-fault attempt have sanitized extracts under `failures/`.

See `RESULTS.md` for the 35-point table and `EVIDENCE_MANIFEST.json` for
source-to-public hashes and redaction counts.
