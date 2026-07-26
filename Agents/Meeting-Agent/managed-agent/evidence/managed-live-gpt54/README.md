# GPT-5.4 Managed Runtime Evidence

This directory contains sanitized validation summaries for the GPT-5.4 / Agent v6 implementation.

- `runtime-validation.json`: dated Prompt Agent, model deployment, Toolbox, Agentic identity, Responses, and least-privilege RBAC contract.
- `dual-input-validation.json`: two materially different real streaming runs with response-ID hashes and distinct analysis, PNG, PPTX, and EML hashes.
- `ui-validation.json`: Windows ARM64 Node and Edge validation plus live Playwright desktop/mobile results.
- `large-input-recovery-validation.json`: the 2026-07-25 large-input failure, capacity correction, detailed SSE error-path fix, and API/browser recovery.

The evidence contains no endpoint, tenant, subscription, identity GUID, raw token, local absolute path, or customer data. It is dated functional evidence, not production certification or a model-quality benchmark.
