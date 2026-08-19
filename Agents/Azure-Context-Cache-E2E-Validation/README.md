# Azure Context Cache E2E Validation

[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![PowerShell 7+](https://img.shields.io/badge/PowerShell-7%2B-5391FE)](https://learn.microsoft.com/powershell/)
[![Upstream pin](https://img.shields.io/badge/AzureContextCache-7d1029a5-247A45)](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)

[中文](README-CN.md) | [Source](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Azure-Context-Cache-E2E-Validation) | [Official upstream](https://github.com/Azure/AzureContextCache)

> Author: Xinyu Wei

A fail-closed harness that verifies the official Azure Context Cache Private Preview Quickstart, then independently scores the real Responses API transcript.

## What's Real vs Test Infrastructure

| Surface | What actually happens | Boundary |
|---|---|---|
| `scripts/run_official_e2e.ps1` | Reads live Azure state, invokes the hash-verified official Quickstart, creates real Azure resources, and sends real Responses API requests | Requires preview onboarding and an authenticated, isolated Azure CLI profile |
| `scripts/verify_upstream.py` | Verifies the official Git commit, origin, clean tree, and 11 Git blob content SHA-256 values | Does not replace or vendor upstream code |
| `scripts/parse_demo_output.py` | Recomputes run count, cache hits, cached tokens, latency, and speedup from captured rows | A transcript with errors, missing rows, or too few warm hits fails closed |
| `tests/fixtures/` | Synthetic transcripts exercise parser success and failure paths | Fixtures never enter the live runtime path |
| `evidence/verified-run-summary.json` | Sanitized single-run observation from the official live path | Not production certification, an SLA, a pricing claim, or a model-quality benchmark |

## What This Repository Validates

The harness proves one bounded chain:

1. The target Azure subscription is enabled and reachable through the selected `AZURE_CONFIG_DIR`.
2. `Microsoft.Storage`, `Microsoft.CognitiveServices`, and `OpenAI.ContextCacheAllowed` are already registered.
3. The official upstream checkout exactly matches commit `7d1029a5e8b59b1805e70992c85ffe6798d2f47a` and its pinned Git blobs.
4. The official `scripts/quickstart.ps1` deploys the Context Cache account, container, linked Azure OpenAI deployment, and data-plane role.
5. Six real Responses API calls complete and enough warm calls report nonzero `cached_tokens`.
6. The parser independently recomputes the evidence instead of trusting a success banner.

The runner does not log in, register the preview feature, use API-key fallback, invent cache results, or delete Azure resources.

## Architecture

![Official execution path](images/architecture.svg)

The public harness owns preflight, provenance, evidence capture, and validation. Azure owns the Private Preview resources. The upstream repository owns deployment and demo behavior.

## Verified Observation

![Sanitized verified observation](images/verified-observation.svg)

The sanitized canary captured six successful calls. Call 1 had `cached_tokens = 0`; calls 2 through 6 each reported `2304` cached tokens. The recomputed warm mean was `3642.4 ms`, compared with `5820 ms` for the first call, an observed `1.597848x` ratio in this one environment.

Those latency values are evidence for that run only. The durable capability signal is the real deployment binding plus nonzero `cached_tokens`; do not generalize the latency ratio or infer cost savings without a separate controlled benchmark and current pricing source.

Subsequent hardened-wrapper probes also exposed transport variability in the official five-request parallel burst. Two complete runs passed; two later runs were rejected after three and four transport errors respectively. They remain visible in [`evidence/validation-history.json`](evidence/validation-history.json) and are not converted into cache scores. This is evidence that the fail-closed gate works, not a production reliability claim.

## Quick Start

### Prerequisites

- PowerShell 7 (`pwsh`) on Windows, Git, Azure CLI, and Python 3.11 or newer
- An Azure subscription approved for the Azure Context Cache Private Preview
- `OpenAI.ContextCacheAllowed` already in `Registered` state
- An isolated `AZURE_CONFIG_DIR` authenticated with the tenant-approved user flow
- Permission to deploy resources and assign `Cognitive Services OpenAI User`
- Available model quota in a supported region

The live run creates billable Azure resources and sends model requests. Choose a unique resource group and name prefix. Inspect the generated evidence before deciding whether to clean up.

### Run the Official E2E

```powershell
$env:AZURE_CONFIG_DIR = "$HOME\.azure-context-cache-validation"
$subscriptionId = "YOUR-SUBSCRIPTION-ID"

az account set --subscription $subscriptionId
az account show --query '{name:name,id:id,tenantId:tenantId,user:user.name}' -o json

pwsh -NoProfile -File .\scripts\run_official_e2e.ps1 `
  -SubscriptionId $subscriptionId `
  -ResourceGroup "rg-context-cache-validation" `
  -Location "centralus" `
  -NamePrefix "ccvalidate" `
  -Runs 6
```

Use `-WhatIf` first to perform read-only Azure preflight without cloning, deploying, or sending requests. The runner creates a unique run directory and a fresh virtual environment outside the source tree, then prints the exact evidence directory. Reusing an existing resource group requires the explicit `-AllowExistingResourceGroup` acknowledgement. A network-restricted environment may pass a separately verified clean checkout through `-ExistingUpstreamDirectory`; the default remains a fresh official clone.

### Validate Locally

```powershell
python -m unittest discover -s tests -v
python scripts\demo_code_validator.py
python scripts\audit_public_content.py
python scripts\validate_repo.py
```

These offline gates require no Azure access. The official upstream lock can also be checked against an existing clean checkout:

```powershell
python scripts\verify_upstream.py `
  --upstream-dir "PATH-TO-AzureContextCache" `
  --lock .\UPSTREAM_LOCK.json
```

## Evidence and Method

The method has three independent proof layers:

| Layer | Authority | Proof |
|---|---|---|
| Source identity | Official Azure Git repository | Commit, origin, clean tree, and Git blob content SHA-256 |
| Azure control plane | Azure Resource Manager | Provider/feature preflight and successful deployment summary |
| Azure data plane | Official Responses API demo | Six parsed call rows, cached token counts, and fail-closed thresholds |

See [Method and lineage](docs/METHOD.md), [public evidence boundary](evidence/README.md), and [scenario manifest](scenario-manifest.json). Public evidence omits cloud identifiers and private raw logs.

## Repository Layout

| Path | Purpose |
|---|---|
| `UPSTREAM_LOCK.json` | Pinned official commit and 11 Git blob content SHA-256 values |
| `scripts/run_official_e2e.ps1` | Live orchestration around the unchanged official Quickstart |
| `scripts/verify_upstream.py` | Cross-platform source identity verifier |
| `scripts/parse_demo_output.py` | Independent transcript parser and cache gate |
| `scripts/demo_code_validator.py` | Static authenticity checks for the live path |
| `scripts/audit_public_content.py` | Value-aware public-boundary scanner |
| `scripts/validate_repo.py` | Deterministic repository quality gate |
| `tests/` | Parser, provenance, runner, scanner, and validator tests |
| `evidence/` | Sanitized observation and evidence manifest |
| `images/` | Architecture and measured-observation diagrams |

## Security and Cleanup

- Never put credentials, Azure CLI caches, endpoints, resource IDs, or raw live logs in this repository.
- Keep each project in a dedicated `AZURE_CONFIG_DIR`; the runner refuses the shared implicit default and any workspace inside the public source tree.
- The runner uses Azure CLI user authentication only for local validation. Long-running services should use an appropriate managed identity or service principal.
- The runner intentionally does not clean up. Review the upstream `scripts/cleanup.ps1`, the generated `run-contract.json`, private `manifest.json`, and the target resource group before any deletion.
- Deletion is a separate, explicit operation. Do not run cleanup against an existing Azure OpenAI account unless its ownership is understood.

See [SECURITY.md](SECURITY.md) for reporting and operational guidance.

## Limitations

- This is a Private Preview validation harness, not an availability or production-readiness guarantee.
- The upstream API version, model version, regions, quota requirements, and onboarding flow can change.
- A single run cannot establish latency distributions, concurrency guarantees, or savings.
- Cache hits may vary between runs. The default gate requires at least three of five warm calls to hit; adjust only with an explicit acceptance contract.
- The harness currently targets the upstream Windows PowerShell Quickstart.
- Upstream does not publish a license file at the pinned commit, so no upstream source is copied into this subtree.

## References

- [Azure/AzureContextCache](https://github.com/Azure/AzureContextCache)
- [Pinned upstream commit](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a)
- [Azure OpenAI prompt caching](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/prompt-caching)
- [Azure CLI configuration isolation](https://learn.microsoft.com/cli/azure/azure-cli-configuration)
- [ATTRIBUTION.md](ATTRIBUTION.md)