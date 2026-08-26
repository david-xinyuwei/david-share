# Public Manifest

This subtree is the complete public source package for **Voice Live API for AIPC**.

Included:

- Windows application source and PyInstaller onedir specification;
- Voice Live, Foundry Agent, and direct Realtime adapters;
- 25 executable tool definitions, with 24 enabled by the default configuration;
- placeholder-only environment configuration;
- offline contract tests and public quality gates;
- sanitized runtime evidence and public visual assets;
- bilingual documentation and customer quick-start guides.

Excluded by design:

- `.env`, API keys, tokens, MSAL caches, passwords, certificates, and private keys;
- tenant, subscription, resource group, resource, endpoint host, account, and recipient identifiers;
- raw runtime logs, raw Copilot sessions, camera frames, generated user content, build output, and virtual environments;
- private investigation notes and customer-specific deployment records.

Run `python scripts/audit_public_content.py` to validate this boundary.
