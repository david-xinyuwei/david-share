# Final Result Validation

This directory contains the compact validation metadata for the final customer-facing results.

- `container-image.json`: immutable ACR reference, image identity, runtime commits, and clean-pull verification status.
- `exact-token-256k.json`: exact 262,144-token 1P1D Prefill validation.
- `h200-reference.json`: customer-provided H200 reference provenance, topology, metric scope, and values; the private source report is not redistributed.
- `prefill-server-info.json`, `decode-server-info.json`: direct worker capacity evidence.
- `runtime-version.txt`: runtime and tuned-configuration identifiers.
- `SHA256SUMS.txt`: integrity manifest for this directory.