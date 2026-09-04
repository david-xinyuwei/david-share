# Microsoft Foundry Managed Compute: Private Endpoint Validation

[![Foundry](https://img.shields.io/badge/Microsoft%20Foundry-Managed%20Compute-0067b8)](https://learn.microsoft.com/azure/foundry/concepts/foundry-models-overview)
[![Private Link](https://img.shields.io/badge/Azure-Private%20Link-0078d4)](https://learn.microsoft.com/azure/foundry/how-to/configure-private-link)
[![Measured](https://img.shields.io/badge/connectivity-public%20403%20%7C%20private%20200-2ea44f)](evidence/connectivity-run.json)
[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/managed-compute-private-endpoint-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/managed-compute-private-endpoint-ci.yml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

This repository answers one question: can a client still call a
`GlobalManagedCompute` deployment through a Private Endpoint after public
network access is disabled on its parent Foundry resource? In one dedicated
run, the outside client changed from `200` to `403`, while a client in the
linked VNet remained at `200`; restoring the saved setting returned the outside
client to `200`.

**Scope:** this proves one inbound client-to-endpoint path. It does not prove
that Managed Compute pods run inside the customer VNet, that Managed Compute
egress uses the customer VNet, zero prompt or completion retention, or
production readiness.

> Author: 魏新宇 (Xinyu Wei)

[English](README.md) | [中文](README-CN.md)

[Start here](#start-here) · [Measured run](#measured-run) · [How it works](#how-the-validation-works) · [Quick start](#quick-start) · [Evidence](#evidence)

---

## Start here

| Goal | Go to | Side effects |
|---|---|---|
| Understand what was measured | [Measured run](#measured-run) and [Evidence](#evidence) | None |
| Check the code and evidence locally | [Tests](#tests) | Local files only; no Azure credentials or endpoint calls |
| Reproduce against your Foundry resource | [Quick start](#quick-start) | Inference calls, Private Endpoint/DNS changes, a temporary public-access change, and model billing |

Runtime scripts require Python 3.11+ and use only the Python standard library.
The live path also requires Azure CLI and an Entra identity allowed to invoke
the deployment.

The acceptance path is deliberately ordered so a broken private path cannot
lock out the operator:

| Stage | Client location | Public network access | Required observation |
|---:|---|---|---|
| 1 | Outside the linked VNet | Enabled | Authenticated Chat Completions `200` |
| 2 | Inside the linked VNet | Enabled | Private DNS plus authenticated `200` |
| 3 | Outside the linked VNet | Disabled | `403` with `Public access is disabled` |
| 4 | Inside the linked VNet | Disabled | Private DNS plus authenticated `200` |
| 5 | Outside the linked VNet | Restored | Authenticated `200` when the saved state was `Enabled` |

Done-when: the parent Foundry resource is back at its saved public network
access setting, and the expected public/private responses all match.

## Responsibility boundary

| Microsoft Foundry and Azure provide | You provide and verify |
|---|---|
| A `GlobalManagedCompute` deployment and its parent Foundry resource | A dedicated non-production Foundry resource; all child projects must be disposable test assets |
| The parent resource's public network access setting | Contributor on the Foundry resource; save and read back the exact prior setting |
| Private Endpoint connection group `account` | A Private Endpoint subnet, Network Contributor, and an `Approved`/`Succeeded` connection |
| Private DNS zone integration | The required zones, VNet links or DNS forwarding, and a client that resolves the endpoint to a private address |
| Entra authentication and data-plane RBAC | One approved inference identity used for every stage |
| Azure Container Instances (ACI), when used as the probe runner | A delegated workload subnet, token delivery through ARM `secureValue`, evidence capture, and an explicit cleanup owner |

**Benefit:** the model URL and deployment do not change when public access is
disabled. **Trade-off:** every client needs both a route to the VNet and DNS that
returns the Private Endpoint address. Networking belongs to the parent Foundry
resource, not to the individual Managed Compute deployment dialog.

## What this repository proves

| Capability | Measured observation | Evidence |
|---|---|---|
| Global Managed Compute was the tested deployment type | The dedicated-run Foundry page showed `qwen--qwen3-32b`, `GlobalManagedCompute`, `Succeeded`, and `H100_80GB` | [Redacted field crops](images/product-ui/deployment-facts.png) |
| Public access enforcement applied to a request addressed to the Managed Compute deployment | Authenticated request outside the VNet returned `403` with `Public access is disabled`; the rejection is an account-boundary result, not proof of where inside the route it was produced | [Run evidence](evidence/connectivity-run.json) |
| Private Endpoint carried a real inference request | The same probe source ran in private-IP ACI, resolved to a private (RFC 1918) address, and returned Chat Completions `200` before and after public network access was disabled; Private Endpoint use is inferred from the private DNS class, not from an address match against the Private Endpoint NIC | [Generated code transcript](evidence/cli-transcript.txt) |
| Safe post-test network state | Public access was restored, public inference returned `200`, and both private ACI probes terminated with exit code `0` | [Post-test record](evidence/raw/post-test-state.json) |
| Resource and billing boundary | Temporary resources remain because cleanup was not authorized; billing continues while Managed Compute remains deployed | [Post-test record](evidence/raw/post-test-state.json) |

Only the parent Foundry resource's `*.services.ai.azure.com` route was tested.
The run does not show whether the Managed Compute deployment exposes any other
inbound hostname. A `403` proves rejection at the account boundary; it does not
locate the rejection inside the Managed Compute route.

## Measured run

The test kept the Foundry account, deployment, endpoint, Entra identity, and
request payload fixed. Only the caller network path and the parent account's
public-network-access setting changed.

Run ID: `managed-compute-private-link-dedicated-20260831` · Date: 2026-08-31 · Scope:
single-run inbound connectivity differential.

| Scenario | DNS | Authenticated HTTP result | Status | Evidence |
|---|---|---:|---|---|
| Client outside VNet, public access enabled | Public address | `200` — real Chat Completions response | PASS | [`public-baseline.json`](evidence/raw/public-baseline.json) |
| Private-IP ACI in linked VNet, public access enabled | Private address | `200` — pre-disable safety check | PASS | [`private-preflight.json`](evidence/raw/private-preflight.json) |
| Client outside VNet, public access disabled | Public address | `403` — public access disabled | PASS | [`public-blocked.json`](evidence/raw/public-blocked.json) |
| Private-IP ACI in linked VNet, public access disabled | Private address | `200` — real Chat Completions response | PASS | [`private-success.json`](evidence/raw/private-success.json) |
| Client outside VNet, public access restored | Public address | `200` — same model endpoint responded; choice content was not retained | PASS | [`public-restored.json`](evidence/raw/public-restored.json) |

The private runner was Azure Container Instances with a private IP in a linked
VNet workload subnet. It sent HTTPS to the privately resolved address; it
was **not Azure Bastion**. Both ACI probes ran the same `probe_endpoint.py`
source hash and exited with code `0`. Generated content and resolved addresses
are omitted; request IDs are represented only as SHA-256 digests. Probe
timestamps establish order, not a latency distribution.

The [generated transcript](evidence/cli-transcript.txt) is the canonical
direct-reading view of the five observations. [Provenance](evidence/provenance.json)
records which fields came from the probe, which fingerprints were derived after
the run, and how to retrieve the exact `762b6978` probe bytes.

## Product evidence

### The deployment was Managed Compute

![Redacted Microsoft Foundry fields showing GlobalManagedCompute, Succeeded, and H100_80GB](images/product-ui/deployment-facts.png)

*Local measurement, run `managed-compute-private-link-dedicated-20260831`,
2026-08-31. Inspect the model, deployment type, provisioning state, and
accelerator. Resource, project, deployment, endpoint, identity, tenant, and
subscription identifiers are omitted. The image identifies the tested object;
the [UI evidence record](evidence/ui-evidence.json) carries its SHA-256 and claim
boundary.*

### Traffic paths

```mermaid
flowchart LR
    OUT[Client outside VNet] -->|Public DNS| PUB[Foundry public endpoint]
    PUB -->|public network access disabled| DENY[403 blocked]
    IN[Private-IP ACI, not Bastion] -->|Private DNS + HTTPS| PE[Private Endpoint]
    PE --> ACCOUNT[Foundry account boundary]
    ACCOUNT --> ROUTE[GlobalManagedCompute route]
    ROUTE --> OK[200 inference response]

    style DENY fill:#fde7e9,stroke:#a4262c
    style OK fill:#dff6dd,stroke:#107c10
```

*Original explanatory diagram based on the measured differential and
[Microsoft's Foundry network-isolation documentation](https://learn.microsoft.com/azure/foundry/how-to/configure-private-link).
It shows client ingress only. The `403` is placed at the account boundary because
the evidence cannot locate it deeper in the route.*

## Executable assets

| Path | Contract |
|---|---|
| [`infra/main.bicep`](infra/main.bicep) | Connects an existing PE subnet to group `account`; either creates and links all three Foundry Private DNS zones or consumes a complete customer-managed zone-ID object |
| [`scripts/probe_endpoint.py`](scripts/probe_endpoint.py) | Sends the same authenticated request and asserts DNS class plus HTTP status without printing a token |
| [`scripts/submit_private_aci_probe.py`](scripts/submit_private_aci_probe.py) | Runs the exact probe source in a private-IP ACI; the container hashes the bytes it executes; the Entra token is injected only as an ARM `secureValue`; an existing name is never updated |
| [`scripts/set_public_network_access.py`](scripts/set_public_network_access.py) | Fails closed unless an Approved PE exists before disabling public access; ETag preconditions reject concurrent account changes (added after the measured run; unit-tested, no live measurement) |
| [`scripts/azure_translator_backtranslate.py`](scripts/azure_translator_backtranslate.py) | Calls Azure AI Translator for Chinese-to-English back-translation; the key is read only from the process environment, while `--check` validates committed evidence without credentials |
| [`tests/`](tests/) | Exercises the CLI entry point, response semantics, zero-PATCH refusal matrix, saved-state restore, raw evidence mutations, and Rule Catalog mutations |
| [`evidence/`](evidence/) | Sanitized run contract, measurements, source lock, UI hashes, and Level 5 rule results |

## How the validation works

| Layer | Actual implementation | Pass condition | Evidence boundary |
|---|---|---|---|
| DNS | [`resolve_addresses`](scripts/probe_endpoint.py) resolves the endpoint; [`classify_addresses`](scripts/probe_endpoint.py) classifies every result as public, private, or mixed | The in-VNet client reports `dnsClass=private` | The retained run did not compare the resolved address with the Private Endpoint NIC |
| Data plane | [`run_probe`](scripts/probe_endpoint.py) sends one Entra-authenticated Chat Completions request | `200` requires `object=chat.completion` and at least one choice; `403` requires the public-access-disabled error category | A network `403` is not interchangeable with an RBAC `403` |
| Control plane | [`change_public_network_access`](scripts/set_public_network_access.py) saves, changes, reads back, and restores the parent resource setting | The requested setting and `Succeeded` state are read back | ETag guards were added after the measured run and have unit tests but no live measurement |

### How customers reach the Private Endpoint

The client type is not the deciding factor. A VM, container, Kubernetes pod, or
on-premises application can call the same model URL when it has a route to the
VNet and DNS resolves that URL to the Private Endpoint address.

| Client location | Network path | DNS requirement |
|---|---|---|
| VM, ACI, or Kubernetes workload in the same or a peered VNet | VNet routing or peering | Link the same Foundry Private DNS zones to every client VNet, or use the organization's DNS resolver |
| On-premises application | ExpressRoute or site-to-site VPN | Conditionally forward the Foundry service zone to an Azure DNS Private Resolver inbound endpoint or an Azure DNS forwarder |
| Developer workstation | Point-to-site VPN, or a VM reached through Azure Bastion | Use the VPN/resolver DNS path; a Bastion VM is a development option, not a requirement |

See [Azure Private Endpoint DNS integration scenarios](https://learn.microsoft.com/azure/private-link/private-endpoint-dns-integration)
and [Azure DNS Private Resolver](https://learn.microsoft.com/azure/dns/dns-private-resolver-overview).
The ACI in this repository is a disposable validation runner, not a prescribed
production client.

### Common misunderstandings

| Misunderstanding | What the code and evidence show |
|---|---|
| “Private Endpoint creates a private copy of the model.” | The deployment and URL stay fixed; the parent Foundry resource changes which network path may reach it. |
| “Private DNS proves the Managed Compute pods are in my VNet.” | The probe proves only that the client resolved a private address and received a valid response. Pod placement is outside scope. |
| “ACI is required to use the model privately.” | ACI was the measured runner. Any client with private routing, private DNS, and an authorized Entra identity can use the endpoint. |

## Quick start

All snippets below use **Bash**. Use a control runner with Azure CLI for account
and deployment commands, a client outside the linked VNet for public probes,
and an approved runner in a separate workload subnet for private probes. Make
this repository available on every probe runner. The private runner needs
Python 3.11+, DNS through the linked VNet, outbound TCP 443 to the endpoint, and
either an authenticated Azure CLI session or an `AZURE_ACCESS_TOKEN` supplied
through a secure process environment. Use the same Entra principal, endpoint,
deployment, prompt, and token limit for every probe.

Azure prerequisites: a dedicated non-production Foundry account whose child
projects are all disposable test assets, commercial cloud, Contributor on the parent Foundry
account, Network Contributor on the target VNet/subnet, and Private DNS Zone
Contributor (or equivalent) where the zones are created. The Private Endpoint
subnet must already exist and allow Private Endpoints. The application/network
owner is responsible for the workload runner and its cleanup.

```bash
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
git -C david-share sparse-checkout set Deep-Learning/Managed-Compute-Private-Endpoint
cd david-share/Deep-Learning/Managed-Compute-Private-Endpoint
```

Confirm the intended Azure account. These commands have no resource side effects:

```bash
az account set --subscription "<subscription-id>"
az account show --query "{subscription:id,tenant:tenantId,user:user.name}" --output json
```

Set the parent account and existing Private Endpoint subnet IDs. The template
derives the VNet from the subnet ID, preventing a PE/DNS-link VNet mismatch.
Preview the exact change:

```bash
FOUNDRY_ACCOUNT_ID="/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<foundry-account>"
PE_SUBNET_ID="/subscriptions/<subscription-id>/resourceGroups/<network-resource-group>/providers/Microsoft.Network/virtualNetworks/<vnet>/subnets/<private-endpoint-subnet>"
VNET_ID="${PE_SUBNET_ID%/subnets/*}"
CURRENT_SUBSCRIPTION_ID="$(az account show --query id --output tsv)"
PE_SUBSCRIPTION_ID="${PE_SUBNET_ID#/subscriptions/}"
PE_SUBSCRIPTION_ID="${PE_SUBSCRIPTION_ID%%/*}"
PRIVATE_ENDPOINT_LOCATION="$(az network vnet show --ids "$VNET_ID" --query location --output tsv)"
test "$PE_SUBSCRIPTION_ID" = "$CURRENT_SUBSCRIPTION_ID" || { echo "Private Endpoint and VNet must use the same subscription." >&2; exit 1; }
test -n "$PRIVATE_ENDPOINT_LOCATION" || { echo "Unable to read the VNet region." >&2; exit 1; }

az deployment group what-if \
  --resource-group "<resource-group>" \
  --template-file infra/main.bicep \
  --parameters \
      foundryAccountResourceId="$FOUNDRY_ACCOUNT_ID" \
      privateEndpointSubnetResourceId="$PE_SUBNET_ID" \
      privateEndpointLocation="$PRIVATE_ENDPOINT_LOCATION"
```

After reviewing the what-if output, deploy the Private Endpoint and supported
Foundry Private DNS zones. In the default mode below, the deployment owns the
three zones and their VNet links:

```bash
az deployment group create \
  --resource-group "<resource-group>" \
  --template-file infra/main.bicep \
  --parameters \
      foundryAccountResourceId="$FOUNDRY_ACCOUNT_ID" \
      privateEndpointSubnetResourceId="$PE_SUBNET_ID" \
      privateEndpointLocation="$PRIVATE_ENDPOINT_LOCATION"
```

For enterprise central DNS, pass the complete typed
`existingPrivateDnsZoneResourceIds` object with the three keys
`cognitiveservices`, `openai`, and `servicesAi`. In that mode the template does
not create zones or VNet links; the DNS owner must pre-link the zones or provide
custom DNS forwarding, and the private probe is the acceptance check. See the
[full procedure](docs/reproduction.md#central-dns-mode).

From a client inside the linked VNet, prove private DNS and inference before
disabling public access:

> This pre-disable `200` is both a fail-closed safety gate and stage 2 of the
> five-stage measured run.

```bash
python scripts/probe_endpoint.py \
  --endpoint "https://<foundry-account>.services.ai.azure.com/openai/v1/chat/completions" \
  --deployment "<managed-compute-deployment>" \
  --expect-dns private \
  --expect-http 200 \
  --prompt "Reply with exactly OK." \
  --max-tokens 4 \
  --output private-probe.json
```

Only after that passes, disable public access and save the exact prior state:

```bash
python scripts/set_public_network_access.py \
  --subscription-id "<subscription-id>" \
  --resource-group "<resource-group>" \
  --account-name "<foundry-account>" \
  --state Disabled \
  --confirm-dedicated-test-account \
  --private-probe-evidence private-probe.json \
  --save-prior-state pna-before.json
```

Keep `pna-before.json` on the trusted control runner and do not commit or edit
it. The current script marks the receipt `applied` only after Azure read-back confirms
`Disabled`, records the account ETag before and after disable, sends both PATCH
operations with `If-Match`, and refuses to restore from an incomplete receipt or
after the account ETag has changed. The 2026-08-31 run executed the earlier
`762b6978` version of this script, which saved and restored the prior state
without ETag preconditions; ETag enforcement has unit tests but no live measurement here.
If the receipt is stuck at `prepared` or an unrelated account change moved the ETag,
the script refuses by design; use the
[manual restore](docs/reproduction.md#manual-restore) instead. The receipt prevents
accidental misuse but is not an authorization boundary: Azure RBAC remains authoritative.

From outside the linked VNet, prove that the authenticated public request is
blocked specifically by the network policy:

```bash
python scripts/probe_endpoint.py \
  --endpoint "https://<foundry-account>.services.ai.azure.com/openai/v1/chat/completions" \
  --deployment "<managed-compute-deployment>" \
  --expect-dns public \
  --expect-http 403 \
  --prompt "Reply with exactly OK." \
  --max-tokens 4 \
  --output public-blocked-probe.json
```

From the workload runner inside the linked VNet, repeat the same request after
public network access is disabled:

```bash
python scripts/probe_endpoint.py \
  --endpoint "https://<foundry-account>.services.ai.azure.com/openai/v1/chat/completions" \
  --deployment "<managed-compute-deployment>" \
  --expect-dns private \
  --expect-http 200 \
  --prompt "Reply with exactly OK." \
  --max-tokens 4 \
  --output private-after-disable-probe.json
```

Restore the value captured before the test; do not hard-code `Enabled`:

```bash
python scripts/set_public_network_access.py \
  --subscription-id "<subscription-id>" \
  --resource-group "<resource-group>" \
  --account-name "<foundry-account>" \
  --restore-state-from pna-before.json
```

If `pna-before.json` records `priorState: Enabled`, prove the restored public
path with the same request:

```bash
python scripts/probe_endpoint.py \
  --endpoint "https://<foundry-account>.services.ai.azure.com/openai/v1/chat/completions" \
  --deployment "<managed-compute-deployment>" \
  --expect-dns public \
  --expect-http 200 \
  --prompt "Reply with exactly OK." \
  --max-tokens 4 \
  --output public-restored-probe.json
```

Done-when: the parent account equals its saved prior public network access state. When that state
was `Enabled`, the final public probe also returns a valid Chat Completions
`200`; when it was `Disabled`, the private path remains `200` and the public
path remains blocked. See
[`docs/reproduction.md`](docs/reproduction.md) for the complete validation and
cleanup sequence.

## Tests

No Azure credentials, GPU, or live endpoint are required. The tests cover URL
and DNS classification, authenticated response semantics, create-only ACI,
zero-PATCH refusal paths, saved-state restore, evidence mutations, bilingual
reader flow, Azure Translator evidence, and the Level 5 rule contract.

```bash
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python scripts/build_evidence.py --check
python scripts/azure_translator_backtranslate.py --check
python scripts/validate_repo.py --public-content-only
python scripts/validate_repo.py
```

Done-when: all tests pass, generated evidence is synchronized, and
`REPO_VALIDATION=PASS`.

## Compatibility notes

- The live run used Azure commercial cloud, Python 3.11+, one
  `GlobalManagedCompute` deployment, and the
  `*.services.ai.azure.com/openai/v1/chat/completions` route.
- The Private Endpoint must be in the same subscription and region as its VNet,
  and its connection must be `Approved` before traffic can pass.
- The default Bicep path manages the three Foundry Private DNS zones. Central
  DNS mode requires pre-existing resolution from the workload network.
- The optional ACI runner requires a separate workload subnet delegated to
  `Microsoft.ContainerInstance/containerGroups`.
- The public Managed Compute deployment how-to remains classic-only. The
  recorded `GlobalManagedCompute` behavior comes from this single 2026-08-31
  run, not from extrapolating the classic endpoint documentation.

## Repository map

| Path | Owner |
|---|---|
| [`infra/`](infra/) | Private Endpoint and Private DNS deployment |
| [`scripts/`](scripts/) | Endpoint probe, ACI submission, public-access change, evidence generation, Azure Translator back-translation, and repository validation |
| [`tests/`](tests/) | Offline behavior, rejection-path, mutation, and reader-flow tests |
| [`evidence/`](evidence/) | Sanitized observations, derived results, source locks, UI ledger, and rule results |
| [`images/`](images/) | Redacted product UI evidence |
| [`docs/`](docs/) | Full ACI reproduction, manual restore, and exemplar alignment |

## Evidence

| Asset | Purpose |
|---|---|
| [`evidence/connectivity-run.json`](evidence/connectivity-run.json) | Sanitized control-plane and public/private data-plane observations |
| [Generated transcript](evidence/cli-transcript.txt) | Derived direct-reading view of the authenticated Python 200/200/403/200/200 observations |
| [`evidence/raw/`](evidence/raw/) | Sanitized source observations from which the connectivity result is generated; scenario files hold only probe- or launcher-emitted fields |
| [`evidence/run-contract.json`](evidence/run-contract.json) | Frozen question, acceptance conditions, and changed variable |
| [`evidence/provenance.json`](evidence/provenance.json) | Public/private evidence boundary, time basis, runner method, and retained-resource state |
| [`evidence/ui-evidence.json`](evidence/ui-evidence.json) | Image hashes, redactions, and per-image claim boundaries |
| [`evidence/translator-back-translation.json`](evidence/translator-back-translation.json) | Live Azure AI Translator Chinese-to-English back-translation, input hashes, metered usage, and numeric-drift result |
| [`evidence/source-lock.json`](evidence/source-lock.json) | Official URLs and immutable documentation commits |
| [`evidence/rule-results.json`](evidence/rule-results.json) | Generated Level 5 rule-by-rule result |

The files under `evidence/raw/` are the earliest public-safe sanitized
observations, not byte-for-byte Azure logs. Their hashes and the repository
validator detect drift inside this repository; they do not independently
authenticate the withheld private source. Fingerprints marked
`derived-post-run` were derived after the run; they are not probe output.

| Evidence class | Assets | What it can support |
|---|---|---|
| `LOCAL_MEASUREMENT` | `evidence/raw/*.json`, product UI image | The recorded five-stage behavior and tested object |
| `DERIVED` | `connectivity-run.json`, generated transcript, rule results | Internal consistency, lineage, and direct reading; not independent source authentication |
| `SOURCE_FACT` | `source-lock.json` | Official Private Endpoint, DNS, and Foundry configuration behavior at the pinned source commits |

Quality status: `ESSENCE_STATUS=PASS`; the recorded run has
`REPRO_STATUS=PASS`. Post-run ETag and in-container hash hardening remain
`LIVE_STATUS=NOT_RUN` and are claimed only as unit-tested code.

The Chinese README is native-authored and independently reviewed; it is not
published machine output. Azure AI Translator was then called for a live
Chinese-to-English back-translation check. The checked-in evidence requires
HTTP `200`, hashed request IDs, current README SHA-256 values, and zero semantic
numeric drift in both English↔Chinese and Chinese→back-translation comparisons.

## Official sources

- [Configure network isolation for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/how-to/configure-private-link)
- [Azure Private Endpoint DNS integration scenarios](https://learn.microsoft.com/azure/private-link/private-endpoint-dns-integration)
- [Azure DNS Private Resolver overview](https://learn.microsoft.com/azure/dns/dns-private-resolver-overview)
- [Azure AI Translator Translate method](https://learn.microsoft.com/azure/ai-services/translator/text-translation/reference/v3/translate)
- [Azure AI Translator authentication](https://learn.microsoft.com/azure/ai-services/translator/text-translation/reference/authentication)
- [Microsoft Foundry Models overview](https://learn.microsoft.com/azure/foundry/concepts/foundry-models-overview)
- [Create a Private Endpoint with Azure CLI](https://learn.microsoft.com/azure/private-link/create-private-endpoint-cli)

The current public Managed Compute deployment how-to is marked classic-only.
This repository therefore does not infer the new `GlobalManagedCompute` behavior
from classic managed online endpoints; the central claim comes from the recorded
2026-08-31 live differential.
