# Full reproduction procedure

## Scope

This procedure validates inbound access to a Microsoft Foundry
`GlobalManagedCompute` inference endpoint. It does not validate pod placement,
outbound VNet injection, content retention, or production readiness.

## Preconditions

- Bash and Azure CLI authenticated to the target subscription on the control runner.
- Python 3.11 or later and this repository on both probe runners.
- Contributor access on the Foundry account and Network Contributor access on
  the target virtual network.
- An existing `GlobalManagedCompute` deployment in Azure commercial cloud.
- An existing customer-managed VNet, a subnet dedicated to Private Endpoints,
  and a separate workload subnet. A VM, Container Apps job, or another approved
  runner in the workload subnet is sufficient.
- The private runner resolves through the linked VNet, can reach the Foundry
  endpoint on TCP 443, and can run as the same approved Entra principal as the
  public runner through Azure CLI or a securely supplied process environment.
- The application/network owner owns creation and cleanup of any temporary
  workload runner. The Foundry resource owner approves and restores PNA changes.

## 1. Deploy the Private Endpoint

```bash
az account set --subscription "<subscription-id>"
az account show --query "{subscription:id,tenant:tenantId,user:user.name}" --output json

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
  --parameters foundryAccountResourceId="$FOUNDRY_ACCOUNT_ID" privateEndpointSubnetResourceId="$PE_SUBNET_ID" privateEndpointLocation="$PRIVATE_ENDPOINT_LOCATION"

az deployment group create \
  --resource-group "<resource-group>" \
  --template-file infra/main.bicep \
  --parameters foundryAccountResourceId="$FOUNDRY_ACCOUNT_ID" privateEndpointSubnetResourceId="$PE_SUBNET_ID" privateEndpointLocation="$PRIVATE_ENDPOINT_LOCATION"
```

Done-when: the Private Endpoint connection is `Approved`, and the three private
DNS zones contain A records for the Foundry account.

### Central DNS mode

The default deployment creates the three supported Private DNS zones and links
them to the VNet. If an enterprise DNS team already owns those zones, add this
complete object to both the what-if and create commands:

```bash
EXISTING_DNS_ZONE_IDS='{"cognitiveservices":"/subscriptions/<dns-subscription-id>/resourceGroups/<dns-resource-group>/providers/Microsoft.Network/privateDnsZones/privatelink.cognitiveservices.azure.com","openai":"/subscriptions/<dns-subscription-id>/resourceGroups/<dns-resource-group>/providers/Microsoft.Network/privateDnsZones/privatelink.openai.azure.com","servicesAi":"/subscriptions/<dns-subscription-id>/resourceGroups/<dns-resource-group>/providers/Microsoft.Network/privateDnsZones/privatelink.services.ai.azure.com"}'

az deployment group what-if \
  --resource-group "<resource-group>" \
  --template-file infra/main.bicep \
  --parameters foundryAccountResourceId="$FOUNDRY_ACCOUNT_ID" privateEndpointSubnetResourceId="$PE_SUBNET_ID" privateEndpointLocation="$PRIVATE_ENDPOINT_LOCATION" existingPrivateDnsZoneResourceIds="$EXISTING_DNS_ZONE_IDS"
```

In central DNS mode, this template creates the Private Endpoint and zone group
but does not create or modify VNet links. The DNS owner must make the three
zones resolvable from the workload subnet through existing links or custom DNS
forwarding. Done-when remains a private DNS resolution plus Chat Completions
`200` from that subnet.

## 2. Prove the private path before disabling public access

Run from a client attached to the linked VNet:

```bash
python scripts/probe_endpoint.py \
  --endpoint "https://<foundry-account>.services.ai.azure.com/openai/v1/chat/completions" \
  --deployment "<managed-compute-deployment>" \
  --expect-dns private \
  --expect-http 200 \
  --prompt "Reply with exactly OK." \
  --max-tokens 4 \
  --output private-before-disable-probe.json
```

Done-when: `dnsClass` is `private`, `httpStatus` is `200`, and `passed` is
`true`.

## 3. Disable public access with a guard

The script refuses to disable public access unless an Approved Private Endpoint
is attached and the fresh private probe is a valid Chat Completions response.
It saves the exact initial PNA state before issuing the PATCH.

```bash
python scripts/set_public_network_access.py \
  --subscription-id "<subscription-id>" \
  --resource-group "<resource-group>" \
  --account-name "<foundry-account>" \
  --state Disabled \
  --private-probe-evidence private-before-disable-probe.json \
  --save-prior-state pna-before.json
```

Done-when: `actualState` is `Disabled`.

Keep `pna-before.json` only on the trusted control runner. Do not commit or edit
it. The script promotes it from `prepared` to `applied` only after Azure confirms
the Disabled state, rejects concurrent PNA drift, and treats Azure RBAC as the
authorization boundary.

## 4. Prove the public/private differential

From outside the VNet:

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

From inside the linked VNet:

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

Do not change the endpoint, deployment, identity, prompt, or token limit.

Done-when: the outside request returns `403`, while the inside request returns
`200`.

## 5. Restore the exact original state after a temporary test

```bash
python scripts/set_public_network_access.py \
  --subscription-id "<subscription-id>" \
  --resource-group "<resource-group>" \
  --account-name "<foundry-account>" \
  --restore-state-from pna-before.json
```

If the saved `priorState` is `Enabled`, run this final public probe:

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

If the saved state is `Disabled`, verify the private `200` remains valid and
the public route remains blocked instead. Delete temporary compute and
networking resources only after retaining sanitized evidence. For a temporary
lab deployment, delete in dependency order: workload runner, Private Endpoint,
Private DNS VNet links, Private DNS zones, and any lab-only VNet. Never delete a
customer-owned VNet. Resource deletion is intentionally not automated by this
repository.
