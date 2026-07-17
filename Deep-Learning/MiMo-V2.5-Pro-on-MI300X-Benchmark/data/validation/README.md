# Final Result Validation

This directory contains the compact validation metadata for the final customer-facing results.

- `container-image.json`: immutable ACR reference, image identity, runtime commits, and clean-pull verification status.
- `decode-fixed-batch-audit.json`: sustained fixed-batch Decode method, KV-pool expansion, steady-state windows, and source-log hashes for the matched-batch 64K points.
- `decode-long-context-evidence.json`: final baked-image long-context Decode method, runtime identity, validated points, and source-artifact hashes.
- `decode-service-log-audit-8k.json`: source-log hashes, actual running-request batch, and direct scheduler generation throughput for the selected 8K headline points.
- `decode-service-log-audit.json`: Decode-node log windows, actual running-request batch, and direct scheduler generation throughput for the long-context points.
- `exact-token-256k.json`: exact 262,144-token 1P1D Prefill validation.
- `h200-reference.json`: customer-provided H200 8K/64K reference provenance, topology, metric scope, and values; the private source report is not redistributed.
- `prefill-server-info.json`, `decode-server-info.json`: direct worker capacity evidence.
- `runtime-version.txt`: runtime and tuned-configuration identifiers.
- `SHA256SUMS.txt`: integrity manifest for this directory.