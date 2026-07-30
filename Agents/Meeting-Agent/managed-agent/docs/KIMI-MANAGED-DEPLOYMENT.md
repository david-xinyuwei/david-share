# Kimi Managed Agent Deployment

[中文](KIMI-MANAGED-DEPLOYMENT-CN.md) | **English** | [Managed implementation](MANAGED-IMPLEMENTATION.md)

This runbook reproduces the current public Managed source contract. It uses placeholders only; keep real tenant, subscription, project, and endpoint values in isolated local CLI profiles and ignored `.azure` state.

## Validated Contract

| Field | Validated value | Scope |
|---|---|---|
| Azure Developer CLI service key | `managed-meeting-agent` | Local `azure.yaml` service selector; not the cloud Agent name |
| Cloud Agent name | `true-meeting-managed-agent` | Foundry Agent resource selected by `agent_reference` |
| Agent version | `6` | Validated immutable version; redeployment can produce a newer version |
| Agent kind / harness | `prompt` / `ghcp` | Foundry-managed Prompt Agent runtime |
| Model | `Kimi-K2.7-Code` | Existing model deployment |
| Model format / version | `MoonshotAI` / `2026-06-12` | Public deployment declaration |
| SKU / capacity | `GlobalStandard` / `50` | One working validation configuration; not universal sizing guidance |
| Toolbox | `my-toolbox` v7 | Validated live Toolbox |
| Public Meeting Skills | `meeting-package`, `mind-map-story`, `presentation-story` | Reproducible source packages in this repository |
| Authentication | Entra + `AgenticIdentityToken` | No model API key in the Managed customer path |

The validated live Toolbox also contained `incident-triage`. This repository does not publish a local `incident-triage` package because no public source package was attested; the current evidence records it as an observed Toolbox capability only.

## Deploy From Public Source

The checked-in source deliberately separates public declarations from private values:

- `agent.yaml` declares `true-meeting-managed-agent` and Kimi.
- `azure.yaml` keeps the `managed-meeting-agent` **service key** required by the deployment command.
- `scripts/render_deployment_source.py` resolves private azd values only into ignored `.azure` state.
- `scripts/deploy-managed-agent.sh` requires isolated Azure CLI and Azure Developer CLI profiles, deploys the service, restores the public YAML, then reconciles Toolbox and Agent runtime state.

Run from an authorized shell after setting project-specific values without printing secrets:

```bash
export AZURE_CONFIG_DIR="$HOME/.azure-<tenant>-<subscription>"
export AZD_CONFIG_DIR="$HOME/.azd-<tenant>-<subscription>"
export AZURE_TENANT_ID="<tenant-id>"
export AZURE_SUBSCRIPTION_ID="<subscription-id>"

bash scripts/deploy-managed-agent.sh
```

The deployment script invokes:

```text
azd deploy managed-meeting-agent
```

Do not replace that service key with `true-meeting-managed-agent`. The cloud Agent name is declared in `agent.yaml` and written to the ignored runtime manifest after reconciliation.

## Start the Local Customer UI

After deployment, use native Windows PowerShell with the same isolated Azure CLI profile:

```powershell
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-<tenant>-<subscription>"
.\scripts\start-ui.ps1 -AzureConfigDir $env:AZURE_CONFIG_DIR
```

The launcher reads endpoint, Agent name, immutable version, model label, and strict-DeckPlan requirement from `.azure/managed-runtime.json`. It fails closed if the Foundry endpoint, Agent reference, Entra token, or runtime manifest is invalid.

## Verification

A valid deployment must prove all of the following independently:

1. Agent status is `active`, with `kind=prompt`, `harness=ghcp`, and model `Kimi-K2.7-Code`.
2. Toolbox access uses `AgenticIdentityToken`; the three public Meeting Skills are present.
3. Direct and browser calls pin the expected Agent name and immutable version.
4. Structured Meeting JSON produces strict Analysis and `DeckPlan`.
5. The local pipeline creates a nonblank mind map, editable six-slide PPTX, and EML with `X-Unsent: 1` and two attachments.
6. The code contains no automatic mail-send path.
7. A Hand/Sandbox observation is reported as a single-session observation, not a fixed SKU, quota, image, persistence contract, or SLA.

See the [sanitized Kimi v6 validation](../evidence/managed-live-westus2/kimi-v6-runtime-validation.json). Historical GPT-5.4 v6/v9 records remain under `evidence/managed-live-gpt54/` and must not be relabeled as current Kimi evidence.
