# Azure Context Cache Customer Evaluation

[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml)
[![CPython 3.11 AMD64](https://img.shields.io/badge/CPython-3.11%20AMD64-3776AB)](https://www.python.org/)
[![PowerShell 7+](https://img.shields.io/badge/PowerShell-7%2B-5391FE)](https://learn.microsoft.com/powershell/)
[![Upstream pin](https://img.shields.io/badge/AzureContextCache-7d1029a5-247A45)](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)

[中文](README-CN.md) | [Source](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Azure-Context-Cache-E2E-Validation) | [Official upstream](https://github.com/Azure/AzureContextCache)

Evaluate explicit context caching for Azure OpenAI applications that repeatedly send the same long instructions, tool definitions, examples, or reference content.

## Customer Problem and Business Value

Enterprise AI applications often resend a large, stable prompt prefix on every request while only the user task or case data changes. Azure Context Cache links an Azure OpenAI deployment to a named cache container so matching requests can reuse the processed stable prefix.

| Business value lever | Why it matters | How the customer should validate it |
|---|---|---|
| Request latency | A cache hit can avoid repeated processing of the stable prefix | Measure latency distributions with the customer's prompt mix and concurrency |
| Input-token economics | Cache reads can use discounted input-token pricing | Combine `cached_tokens`, actual hit rate, and current Azure pricing |
| Capacity efficiency | Reusing repeated-prefix computation can free model capacity | Run a controlled throughput test at the target load |
| Governance | The named cache resource is deployed in the customer's subscription, region, and RBAC boundary with a configured TTL | Confirm target-region support, access controls, lifecycle, and data requirements |

> The [pinned official Quickstart](https://github.com/Azure/AzureContextCache/tree/7d1029a5e8b59b1805e70992c85ffe6798d2f47a) describes latency, cost, and throughput as product value levers. This repository proves cache use in one approved environment; it does not quantify the customer's savings or production performance.

## Workload Fit

| Decision | Workload pattern | Evaluation guidance |
|---|---|---|
| **GO** | Long system/developer instructions, stable tool catalogs, few-shot examples, or shared policies | Place reusable content first and changing task data last |
| **GO** | Customer support, code/compliance review, document-heavy assistants, and controlled agent workflows | Proceed when rules, tools, or reference material repeat across requests |
| **CONDITIONAL** | Append-only conversations with a stable early history | Validate that the early prefix remains byte-identical |
| **LOW PRIORITY** | Short prompts or requests whose first section changes frequently | Reusable prefix overlap is limited |
| **LOW PRIORITY** | One-off requests or highly personalized content at the beginning of every prompt | Cache reuse is unlikely |
| **CONDITIONAL** | A business case requiring an exact savings or throughput commitment | Build a separate customer-data benchmark and current pricing model |

## Customer Architecture

![Azure Context Cache customer application architecture](images/customer-architecture.svg)

1. The customer application places reusable instructions, tools, examples, and shared references in a stable prefix.
2. Per-request user tasks and case data are appended as the dynamic suffix.
3. The application continues to call the Azure OpenAI Responses API; the linked deployment consults the Context Cache container for a matching prefix.
4. The application observes `cached_tokens`, latency, and request outcomes to validate fit with the customer's traffic.

The Context Cache container is an Azure resource in the customer subscription. The pinned Private Preview Quickstart configures the cache account, model-specific container, TTL, and `contextCacheContainerId` binding.

## What This Repository Proves

The official Quickstart pinned to commit `7d1029a5e8b59b1805e70992c85ffe6798d2f47a` was validated end to end in an approved Private Preview subscription.

| Validation signal | Observed result | Evidence meaning |
|---|---:|---|
| Real Responses API calls | `6/6` completed | The official deployment and data-plane path completed |
| Warm cache calls | `5/5` reported cache hits | The linked Context Cache served the warm calls |
| Cached input tokens | `2304` on every warm call | A consistent nonzero cache signal was observed |
| Evidence handling | 2 later incomplete runs rejected | Transport failures were not converted into passes |

**Recommended next step:** after confirming Preview onboarding, permissions, quota, and regional availability, run the same validation with representative prompts in the customer-owned Azure environment.

> **Evidence boundary:** this is a single-run capability observation, not a production-readiness, availability, cost-saving, throughput, or latency guarantee.

This repository evaluates the pinned Private Preview resource path based on `Microsoft.Storage/contextCaches` and `contextCacheContainerId`. The general Azure OpenAI prompt-caching guidance can differ by model family and API surface; confirm the target model and current official documentation separately.

## Test Information, Procedure, and Evidence

### Test Information

| Item | Verified value |
|---|---|
| Observation date | `2026-08-18` |
| Execution plane | `LOCAL_WINDOWS` |
| Azure region | `centralus` |
| Official source | `Azure/AzureContextCache` at commit `7d1029a5e8b59b1805e70992c85ffe6798d2f47a` |
| Runtime | CPython `3.11.9 AMD64`; orchestration through PowerShell 7 and Azure CLI user authentication |
| Deployment | `gpt-5.4`, model version `2026-03-05-contextcache`, Responses API `preview` |
| Cache contract | Model-specific Context Cache container, 7-day TTL, explicit `contextCacheContainerId` binding |
| Request pattern | 1 warm-up request followed by 5 parallel requests |

This table describes the sanitized validation environment, not a supported-region or production-sizing recommendation.

### Test Procedure

1. **Verify the official source.** `scripts/verify_upstream.py` resolves the pinned Git object, verifies the SHA-256 of all 25 executable inputs, and materializes only those verified bytes outside the public source tree.
2. **Run the read-only Azure preflight.** `scripts/run_official_e2e.ps1 -WhatIf` checks the active subscription, a live ARM read, required resource providers, the gated feature, runtime architecture, and target-region prerequisites without deploying resources or sending model requests.
3. **Deploy the official Quickstart.** The live runner installs the exact hashed Windows AMD64 CPython 3.11 dependencies and invokes the byte-identical official `scripts/quickstart.ps1` with `-SkipPython` in a private run directory.
4. **Exercise the data plane.** The official demo sends one warm-up request and five parallel Responses API requests with a shared stable prefix.
5. **Validate independently.** `scripts/parse_demo_output.py` parses all six call rows and rejects missing rows, transport errors, zero thresholds, zero latency, or insufficient warm hits. `scripts/validate_arm_summary.py` separately verifies deployment success, model identity, cache-container ID, provider, TTL, and deployment binding.
6. **Run offline regression gates.** The unit suite, authenticity validator, public-content audit, repository gate, dependency check, PowerShell parse check, CI matrix, and CodeQL run against the published commit.

### Test Scripts

| Script or suite | Role in the test | Fail-closed behavior |
|---|---|---|
| [`scripts/run_official_e2e.ps1`](scripts/run_official_e2e.ps1) | Azure preflight, verified-source materialization, official Quickstart execution, transcript capture, and evidence orchestration | Stops on profile reuse, wrong runtime, pre-existing resource group, Azure timeout/error, nonzero official exit, or failed evidence validation |
| [`scripts/verify_upstream.py`](scripts/verify_upstream.py) | Verifies the pinned repository, commit, and 25 Git-blob SHA-256 values | Refuses a missing/mismatched blob or nonempty output directory |
| [`scripts/parse_demo_output.py`](scripts/parse_demo_output.py) | Parses call-level latency and token fields and computes the cache verdict | Rejects transport errors, malformed/missing calls, zero thresholds/latency, and insufficient warm hits |
| [`scripts/validate_arm_summary.py`](scripts/validate_arm_summary.py) | Cross-checks ARM deployment state and the AOAI-to-cache binding | Rejects failed deployment, missing fields, wrong model/provider/TTL, or inconsistent resource IDs |
| [`scripts/demo_code_validator.py`](scripts/demo_code_validator.py) | Checks that the harness uses the real official path rather than hardcoded or mock outcomes | Rejects simulated product behavior and source/runtime contract drift |
| [`scripts/audit_public_content.py`](scripts/audit_public_content.py) | Scans the public subtree for secrets, concrete cloud identifiers, unsafe links, reparse points, and unsupported formats | Any public-boundary finding fails the release gate |
| [`scripts/validate_repo.py`](scripts/validate_repo.py) and [`tests/`](tests/) | Recomputes evidence arithmetic/hashes and tests parser, ARM, source-lock, orchestration, and public-boundary branches | Any invariant or regression failure returns a nonzero exit code |

### Sanitized Test Log

The following human-readable excerpt is rendered from [`evidence/verified-run-summary.json`](evidence/verified-run-summary.json). It is **not** the private raw stdout/stderr; cloud identifiers, endpoints, identities, and deployment records remain excluded.

```text
[run] observed_at=2026-08-18 upstream_commit=7d1029a5e8b59b1805e70992c85ffe6798d2f47a
[environment] execution_plane=LOCAL_WINDOWS region=centralus python="3.11.9 AMD64"
[deployment] model=gpt-5.4 model_version=2026-03-05-contextcache api_version=preview cache_ttl_days=7
[call 1] latency_ms=5820 input_tokens=2607 cached_tokens=0    output_tokens=200
[call 2] latency_ms=3791 input_tokens=2571 cached_tokens=2304 output_tokens=126
[call 3] latency_ms=3751 input_tokens=2681 cached_tokens=2304 output_tokens=200
[call 4] latency_ms=3671 input_tokens=2675 cached_tokens=2304 output_tokens=200
[call 5] latency_ms=3215 input_tokens=2570 cached_tokens=2304 output_tokens=133
[call 6] latency_ms=3784 input_tokens=2540 cached_tokens=2304 output_tokens=200
[summary] successful_calls=6 warm_hits=5/5 warm_cached_tokens=2304 verdict=PASS
```

These latency values are retained for auditability only. One run cannot establish a latency distribution or a production performance claim.

### Test Results

The checked-in [`validation-history.json`](evidence/validation-history.json) preserves both complete and rejected runs:

| Date | Execution path | Completed calls | Transport errors | Cache result | Verdict |
|---|---|---:|---:|---:|---|
| `2026-08-18` | `official-baseline` | 6 | 0 | 5/5 warm hits | **PASS** |
| `2026-08-19` | `public-wrapper-reference` | 6 | 0 | 4/5 warm hits | **PASS** |
| `2026-08-19` | `hardened-wrapper-probe-1` | 3 | 3 | Not scored | **REJECTED — INCOMPLETE** |
| `2026-08-19` | `hardened-wrapper-probe-2` | 2 | 4 | Not scored | **REJECTED — INCOMPLETE** |

| Published-commit quality gate | Result | Evidence |
|---|---:|---|
| Deterministic unit tests | `38/38` passed | `python -m unittest discover -s tests -v` |
| Authenticity, public boundary, and repository gates | `3/3` passed | `demo_code_validator.py`, `audit_public_content.py`, `validate_repo.py` |
| Windows/Ubuntu × Python 3.11/3.13 CI matrix | `4/4` jobs passed | [GitHub Actions run 32270323872](https://github.com/david-xinyuwei/david-share/actions/runs/32270323872) |
| CodeQL analyzers | `7/7` jobs passed | [CodeQL run 32270323901](https://github.com/david-xinyuwei/david-share/actions/runs/32270323901) |

The live result and the offline gates answer different questions: the live run proves the bounded Azure product path, while the offline suite proves that the evidence parser, source lock, orchestration controls, and public release contract continue to behave as specified.

## Customer Evaluation Path

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

Use `-WhatIf` first to perform time-bounded, read-only Azure preflight without cloning, deploying, or sending requests. A live run requires a new unique resource group, creates a unique private evidence directory outside the source tree, and does not clean up Azure resources automatically. For restricted networks, `-ExistingUpstreamDirectory` may reference a checkout at the pinned commit; see [Method and lineage](docs/METHOD.md) for provenance controls.

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

## Evidence Boundary and Validation Method

The method has three independent proof layers:

| Layer | Authority | Proof |
|---|---|---|
| Source identity | Official Azure Git repository | Pinned commit and verified executable inputs |
| Azure control plane | Azure Resource Manager | Provider/feature preflight plus deployment, AOAI model, cache-container ID, provider, and TTL binding |
| Azure data plane | Official Responses API demo | Six parsed call rows, cached token counts, and fail-closed thresholds |

See [Method and lineage](docs/METHOD.md), [public evidence boundary](evidence/README.md), [sanitized run summary](evidence/verified-run-summary.json), and [validation history](evidence/validation-history.json). Public evidence omits cloud identifiers and private raw logs.

## Security and Operations

- Never put credentials, Azure CLI caches, endpoints, resource IDs, or raw live logs in this repository. The scanner also rejects symlinks, reparse points, unsupported public file formats, and common token/SAS/connection-string forms.
- Keep each project in a dedicated `AZURE_CONFIG_DIR`; the runner refuses the shared implicit default and any workspace inside the public source tree.
- The runner uses Azure CLI user authentication only for local validation. Long-running services should use an appropriate managed identity or service principal.
- The runner requires a new resource group and intentionally does not clean up. Review the upstream `scripts/cleanup.ps1`, the generated `run-contract.json`, private `manifest.json`, and the target resource group before any deletion.
- Deletion is a separate, explicit operation. Do not run cleanup against an existing Azure OpenAI account unless its ownership is understood.

See [SECURITY.md](SECURITY.md) for reporting and operational guidance.

## Product and Evidence Limits

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