# Public Subtree Manifest

The public `managed-agent/` subtree is built from an explicit allowlist in `scripts/build_customer_package.py`.

Included:

- Managed runtime source and tests
- React UI, BFF, and Playwright tests
- Deployment declarations with placeholders
- Synthetic examples and the two analysis JSON fixtures required by tests
- Sanitized cloud, Skill, UI, and parity summaries
- Bilingual documentation and security policy

Excluded:

- `.azure`, `.env`, local credentials, `password.txt`
- Runtime sessions, logs, generated artifacts, delivery ZIPs
- `node_modules`, virtual environments, caches, test results
- Raw Toolbox responses, tenant URLs, identities, and local absolute paths
- Legacy AOAI screenshots, videos, and evidence already represented by the classic root implementation
- Classic sample-run PPTX, PNG, SVG, and EML binaries; the repository root already owns those artifacts
