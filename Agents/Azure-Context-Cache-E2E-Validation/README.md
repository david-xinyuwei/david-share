# Azure Context Cache E2E Validation

[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml)
[![CPython 3.11 AMD64](https://img.shields.io/badge/CPython-3.11%20AMD64-3776AB)](https://www.python.org/)
[![PowerShell 7+](https://img.shields.io/badge/PowerShell-7%2B-5391FE)](https://learn.microsoft.com/powershell/)
[![Upstream pin](https://img.shields.io/badge/AzureContextCache-7d1029a5-247A45)](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)

[中文](README-CN.md) | [Source](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Azure-Context-Cache-E2E-Validation) | [Official upstream](https://github.com/Azure/AzureContextCache)

Official Azure Context Cache Private Preview Quickstart validated end to end: `6/6` real Responses API calls completed, and all `5/5` warm calls reported `2304` cached tokens.

## Validated Result

The official Quickstart pinned to commit `7d1029a5e8b59b1805e70992c85ffe6798d2f47a` was validated end to end in an approved Private Preview subscription.

| Validation signal | Observed result | What it establishes |
|---|---:|---|
| Real Responses API calls | `6/6` completed | The official deployment and data-plane path completed |
| Warm cache calls | `5/5` reported cache hits | The linked Context Cache served the warm calls |
| Cached input tokens | `2304` on every warm call | A consistent nonzero cache signal was observed |
| Evidence handling | 2 later incomplete runs rejected | Transport failures were not converted into passes |

**Recommended next step:** after confirming Preview onboarding, permissions, quota, and regional availability, run the same validation in the customer-owned Azure environment.

> **Boundary:** this is a single-run capability observation, not a production-readiness, availability, cost-saving, or latency guarantee. Two later incomplete runs were rejected by the fail-closed gate and excluded from the cache result.

## Quick Start

### Prerequisites

- PowerShell 7 (`pwsh`) on Windows, Git, Azure CLI, and 64-bit CPython 3.11 on AMD64 Windows
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

Use `-WhatIf` first to perform time-bounded, read-only Azure preflight without cloning, deploying, or sending requests. A live run requires a new unique resource group, creates a unique private run directory and fresh virtual environment outside the source tree, and prints the exact evidence directory. A network-restricted environment may pass a checkout at the pinned commit as a Git object source through `-ExistingUpstreamDirectory`; uncommitted worktree bytes are ignored, and the runner exports and executes only the 25 hash-verified Git blobs. The default remains a fresh official clone.

### Validate Locally

```powershell
python -m unittest discover -s tests -v
python scripts\demo_code_validator.py
python scripts\audit_public_content.py
python scripts\validate_repo.py
```

These offline gates require no Azure access. The official upstream lock can also be checked against an existing checkout at the pinned commit:

```powershell
python scripts\verify_upstream.py `
  --upstream-dir "PATH-TO-AzureContextCache" `
  --lock .\UPSTREAM_LOCK.json `
  --output "EMPTY-PRIVATE-OUTPUT-DIRECTORY"
```

## What Was Validated

1. The selected Azure subscription was enabled, and the required providers and `OpenAI.ContextCacheAllowed` feature were registered.
2. The official source matched the pinned commit, origin, and all 25 executable-input SHA-256 values.
3. The byte-identical official Quickstart deployed the Context Cache account, container, linked Azure OpenAI deployment, and data-plane role.
4. The runner independently verified deployment state, model version, container binding, provider, and TTL.
5. Six Responses API call rows were captured and independently recomputed; missing rows, errors, zero thresholds, and weak cache evidence fail closed.

The runner does not log in, register the preview feature, use API-key fallback, invent cache results, or delete Azure resources.

## Architecture

![Official execution path](images/architecture.svg)

Azure owns the Private Preview resources. The official upstream owns deployment and demo behavior. This repository owns source verification, bounded orchestration, evidence capture, and independent validation.

## Evidence and Audit Trail

The method has three independent proof layers:

| Layer | Authority | Proof |
|---|---|---|
| Source identity | Official Azure Git repository | Commit, origin, and Git blob content SHA-256; external worktree bytes are ignored |
| Azure control plane | Azure Resource Manager | Provider/feature preflight plus deployment, AOAI model, cache-container ID, provider, and TTL binding |
| Azure data plane | Official Responses API demo | Six parsed call rows, cached token counts, and fail-closed thresholds |

See [Method and lineage](docs/METHOD.md), [public evidence boundary](evidence/README.md), [sanitized run summary](evidence/verified-run-summary.json), and [validation history](evidence/validation-history.json). Public evidence omits cloud identifiers and private raw logs.

## Observed Run Details

![Sanitized verified observation](images/verified-observation.svg)

Call 1 reported `cached_tokens = 0`; calls 2 through 6 each reported `2304` cached tokens. The recomputed warm mean was `3642.4 ms`, compared with `5820 ms` for the first call, an observed ratio of `1.597848x` in this one environment.

The latency values describe that run only. The durable capability signal is the verified deployment binding plus nonzero `cached_tokens`. Do not generalize the ratio or infer cost savings without a separate controlled benchmark and current pricing source.

Two complete runs passed. Two later runs were rejected after three and four transport errors respectively. Rejected runs remain visible in the validation history and are not scored as cache results.

## Validation Design and Boundaries

| Surface | What actually happens | Boundary |
|---|---|---|
| `scripts/run_official_e2e.ps1` | Reads live Azure state, invokes the verified official Quickstart, creates real Azure resources, and sends real Responses API requests | Requires preview onboarding and an authenticated, isolated Azure CLI profile |
| `scripts/verify_upstream.py` | Verifies the commit, origin, and all 25 executable inputs, then materializes the exact Git blob bytes privately | The external worktree is never executed |
| `scripts/parse_demo_output.py` | Recomputes call count, cache hits, cached tokens, and latency fields | Errors, missing rows, zero thresholds, zero latency, or too few warm hits fail closed |
| `scripts/validate_arm_summary.py` | Verifies deployment success and the model/cache binding across three ARM resources | Missing, failed, or mismatched control-plane evidence fails closed |
| `tests/fixtures/` | Exercises deterministic success and failure branches | Synthetic fixtures never enter the live runtime path |

## Repository Layout

| Path | Purpose |
|---|---|
| `UPSTREAM_LOCK.json` | Pinned official commit and all 25 executable-input Git blob content SHA-256 values |
| `requirements-live-win-py311.lock` | Exact Windows AMD64 CPython 3.11 wheels and artifact SHA-256 values |
| `scripts/run_official_e2e.ps1` | Live orchestration around the unchanged official Quickstart |
| `scripts/verify_upstream.py` | Cross-platform source identity verifier |
| `scripts/parse_demo_output.py` | Independent transcript parser and cache gate |
| `scripts/validate_arm_summary.py` | Independent ARM deployment and resource-binding gate |
| `scripts/demo_code_validator.py` | Static authenticity checks for the live path |
| `scripts/audit_public_content.py` | Value-aware public-boundary scanner |
| `scripts/validate_repo.py` | Deterministic repository quality gate |
| `tests/` | Parser, provenance, runner, scanner, and validator tests |
| `evidence/` | Sanitized observation and evidence manifest |
| `images/` | Architecture and measured-observation diagrams |

## Security and Cleanup

- Never put credentials, Azure CLI caches, endpoints, resource IDs, or raw live logs in this repository. The scanner also rejects symlinks, reparse points, unsupported public file formats, and common token/SAS/connection-string forms.
- Keep each project in a dedicated `AZURE_CONFIG_DIR`; the runner refuses the shared implicit default and any workspace inside the public source tree.
- The runner uses Azure CLI user authentication only for local validation. Long-running services should use an appropriate managed identity or service principal.
- The runner requires a new resource group and intentionally does not clean up. Review the upstream `scripts/cleanup.ps1`, the generated `run-contract.json`, private `manifest.json`, and the target resource group before any deletion.
- Deletion is a separate, explicit operation. Do not run cleanup against an existing Azure OpenAI account unless its ownership is understood.

See [SECURITY.md](SECURITY.md) for reporting and operational guidance.

## Limitations

- This is a Private Preview validation harness, not an availability or production-readiness guarantee.
- The upstream API version, model version, regions, quota requirements, and onboarding flow can change.
- A single run cannot establish latency distributions, concurrency guarantees, or savings.
- Cache hits may vary between runs. The default gate requires at least three of five warm calls to hit, and the threshold cannot be zero; adjust only with an explicit acceptance contract.
- The harness currently targets the upstream Windows PowerShell Quickstart.
- The live dependency lock is intentionally limited to the verified Windows AMD64 CPython 3.11 runtime.
- Upstream does not publish a license file at the pinned commit. No upstream source is checked into this subtree; the runner creates a temporary private execution copy from verified Git blobs.

## References

- [Azure/AzureContextCache](https://github.com/Azure/AzureContextCache)
- [Pinned upstream commit](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a)
- [Azure OpenAI prompt caching](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/prompt-caching)
- [Azure CLI configuration isolation](https://learn.microsoft.com/cli/azure/azure-cli-configuration)
- [ATTRIBUTION.md](ATTRIBUTION.md)

Maintainer: Xinyu Wei