# Managed Runtime Evidence

These files are sanitized validation summaries, not live service credentials or timeless status claims.

- `public-v2-source-manifest.json`: hashes that bind the public Agent, instructions, Skill, and deployment declaration to the successful v2 deployment.
- `public-v2-agent-reference-validation.json`: non-stream and stream calls that validated `managed-meeting-agent` version `2`, including real delta counts and a hashed response ID.
- `public-v2-deployment-validation.json`: independently parsed PNG, six-slide PPTX, and unsent EML contracts for two materially different v2 inputs.
- `artifact-validation.json`: historical v1 artifact validation retained for comparison.
- `parity-manifest.json`: byte-for-byte hashes for shared classic and managed modules.
- `toolbox-skill-validation.json`: dated hash from the Toolbox Skill validation run.
- `ui-live-validation.json`: dated browser validation summary with cloud identifiers redacted.

Raw HTTP headers, tenant URLs, identities, request bodies, runtime logs, and local absolute paths are intentionally excluded from the public repository. The v2 evidence is dated and must be revalidated after source or target-environment changes.
