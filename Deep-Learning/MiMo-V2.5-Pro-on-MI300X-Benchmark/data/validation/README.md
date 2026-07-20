# Final Result Validation

This directory contains the compact validation metadata for the final customer-facing results.

- `container-image.json`: public runtime alias, immutable digest/image identity, runtime commits, and clean-pull verification status. Private registry coordinates are intentionally withheld.
- `decode-fixed-batch-audit.json`: exact 64K/1K BS16 two-run method, optimized-kernel evidence, transition-guard windows, source-log hashes, and separately labeled output8K diagnostics.
- `../evidence/exact64-fixed-acceptance/`: sanitized client summaries and scheduler windows used by `scripts/analyze_exact64_evidence.py` to rebuild the exact64 headline.
- `controlled-isl-evidence.json`: 128K/192K Prefill and steady-BS4 Decode method, fixed-acceptance scope, runtime identity, and disclosed deltas.
- `../evidence/controlled-isl-128k-192k/`: sanitized summaries and scheduler windows used by `scripts/analyze_controlled_isl_evidence.py`.
- `decode-long-context-evidence.json`: final baked-image long-context Decode method, runtime identity, validated points, and source-artifact hashes.
- `decode-service-log-audit-8k.json`: source-log hashes, actual running-request batch, and direct scheduler generation throughput for the selected 8K headline points.
- `decode-service-log-audit.json`: Decode-node log windows, actual running-request batch, and direct scheduler generation throughput for the long-context points.
- `exact-token-256k.json`: exact 262,144-token 1P1D Prefill validation.
- `h200-reference.json`: customer-provided H200 8K/64K reference provenance, topology, metric scope, and selected numeric excerpts; the private source report is not redistributed, and external sharing authorization must be confirmed by the repository owner.
- `prefill-server-info.json`, `decode-server-info.json`: direct worker capacity evidence.
- `runtime-version.txt`: runtime and tuned-configuration identifiers.
- `SHA256SUMS.txt`: integrity manifest for this directory.