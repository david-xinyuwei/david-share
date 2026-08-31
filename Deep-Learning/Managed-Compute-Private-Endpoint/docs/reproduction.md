# Full reproduction procedure

## Scope

This procedure validates inbound access to a Microsoft Foundry
`GlobalManagedCompute` inference endpoint. It does not validate pod placement,
outbound VNet injection, content retention, or production readiness.

## Preconditions

- Bash and Azure CLI authenticated to the target subscription on the control runner.
- Python 3.11 or later and this repository on the public/control runner.
- Contributor access on the Foundry account and Network Contributor access on
  the target virtual network.
- An existing `GlobalManagedCompute` deployment in Azure commercial cloud.
- A dedicated non-production Foundry account. A new project under a shared
  account is not sufficient because PNA and Private Endpoint are account-level
  controls.
- An existing customer-managed VNet, a subnet dedicated to Private Endpoints,
  and a separate workload subnet. The ACI path below requires the workload
  subnet to be delegated to `Microsoft.ContainerInstance/containerGroups`.
- The private runner resolves through the linked VNet, can reach the Foundry
  endpoint on TCP 443, and can run as the same approved Entra principal as the
  public runner through Azure CLI or a securely supplied process environment.
- The application/network owner owns creation and cleanup of any temporary
  workload runner. The Foundry resource owner approves and restores PNA changes.

The measured path used **private-IP Azure Container Instances (ACI)** in the
workload subnet. It did not use Azure Bastion. The control runner acquired the
approved Entra data-plane token, submitted it to ARM as a container environment
`secureValue`, and embedded the exact bytes of `scripts/probe_endpoint.py` in a
`restartPolicy=Never` container. The ACI then resolved the Foundry hostname
privately and sent HTTPS directly through the Private Endpoint. The secure value
is not returned by the ACI read API or printed by the probe.
The launcher refuses any existing container-group name and sends the create PUT
with `If-None-Match: *`; it never updates an existing ACI.

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

## 2. Prove the public baseline and private path

From outside the VNet, first prove that the authenticated endpoint works while
PNA is enabled:

```bash
python scripts/probe_endpoint.py \
  --endpoint "https://<foundry-account>.services.ai.azure.com/openai/v1/chat/completions" \
  --deployment "<managed-compute-deployment>" \
  --expect-dns public \
  --expect-http 200 \
  --prompt "Reply with exactly OK." \
  --max-tokens 4 \
  --output public-baseline-probe.json
```

For the private preflight, create a private-IP ACI from the control runner. The
launcher embeds the exact probe source and never forwards the ARM token into the
container. Use a unique ACI name for each probe:

```bash
RUN_ID="managed-compute-private-link-$(date -u +%Y%m%dT%H%M%SZ)"
WORKLOAD_SUBNET_ID="/subscriptions/<subscription-id>/resourceGroups/<network-resource-group>/providers/Microsoft.Network/virtualNetworks/<vnet>/subnets/<workload-subnet>"
PRIVATE_BEFORE_ACI="aci-mcpe-before-<unique-suffix>"

python scripts/submit_private_aci_probe.py \
  --subscription-id "<subscription-id>" \
  --resource-group "<resource-group>" \
  --container-group-name "$PRIVATE_BEFORE_ACI" \
  --location "<vnet-region>" \
  --subnet-id "$WORKLOAD_SUBNET_ID" \
  --endpoint "https://<foundry-account>.services.ai.azure.com/openai/v1/chat/completions" \
  --deployment "<managed-compute-deployment>" \
  --run-id "$RUN_ID" \
  --output private-before-submit.json

wait_for_aci_probe() {
  local name="$1" state exit_code
  for _ in $(seq 1 60); do
    IFS=$'\t' read -r state exit_code <<< "$(az container show \
      --resource-group "<resource-group>" \
      --name "$name" \
      --query '[containers[0].instanceView.currentState.state,containers[0].instanceView.currentState.exitCode]' \
      --output tsv)"
    if [ "$state" = "Terminated" ]; then
      test "$exit_code" = "0"
      return
    fi
    sleep 5
  done
  echo "ACI probe did not terminate within 300 seconds" >&2
  return 1
}

wait_for_aci_probe "$PRIVATE_BEFORE_ACI"

az container show \
  --resource-group "<resource-group>" \
  --name "$PRIVATE_BEFORE_ACI" \
  --query '{provisioningState:provisioningState,containerState:containers[0].instanceView.currentState.state,exitCode:containers[0].instanceView.currentState.exitCode}' \
  --output json

az container logs \
  --resource-group "<resource-group>" \
  --name "$PRIVATE_BEFORE_ACI" \
  --container-name probe > private-before-disable-probe.json
```

The submit result (`201`, `Pending`, or `Creating`) proves only that ARM accepted
the container group. Done-when: the container reaches `Terminated` with exit code
`0`, and its log JSON has `dnsClass=private`, `httpStatus=200`,
`object=chat.completion`, `choiceCount>0`, and `passed=true`.

## 3. Disable public access with a guard

The script refuses to disable public access unless an Approved Private Endpoint
is attached and the fresh private probe is a valid Chat Completions response.
It saves the exact initial PNA state before issuing the PATCH.
The receipt stores the account ETag before and after disable. Disable and restore
use `If-Match`, so a concurrent or ABA account change fails instead of being
overwritten.

```bash
python scripts/set_public_network_access.py \
  --subscription-id "<subscription-id>" \
  --resource-group "<resource-group>" \
  --account-name "<foundry-account>" \
  --state Disabled \
  --confirm-dedicated-test-account \
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

Create a second private-IP ACI after PNA is disabled. This runs the same probe
source through the same workload subnet; it does not reuse the completed
preflight container:

```bash
PRIVATE_AFTER_ACI="aci-mcpe-after-<unique-suffix>"

python scripts/submit_private_aci_probe.py \
  --subscription-id "<subscription-id>" \
  --resource-group "<resource-group>" \
  --container-group-name "$PRIVATE_AFTER_ACI" \
  --location "<vnet-region>" \
  --subnet-id "$WORKLOAD_SUBNET_ID" \
  --endpoint "https://<foundry-account>.services.ai.azure.com/openai/v1/chat/completions" \
  --deployment "<managed-compute-deployment>" \
  --run-id "$RUN_ID" \
  --output private-after-submit.json

wait_for_aci_probe "$PRIVATE_AFTER_ACI"

az container show \
  --resource-group "<resource-group>" \
  --name "$PRIVATE_AFTER_ACI" \
  --query '{provisioningState:provisioningState,containerState:containers[0].instanceView.currentState.state,exitCode:containers[0].instanceView.currentState.exitCode}' \
  --output json

az container logs \
  --resource-group "<resource-group>" \
  --name "$PRIVATE_AFTER_ACI" \
  --container-name probe > private-after-disable-probe.json
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
the public route remains blocked instead. Both ACI probes use
`restartPolicy=Never`, but the terminated container-group resources still exist
until deleted. Delete temporary compute and networking resources only after
retaining sanitized evidence and obtaining the resource owner's explicit
authorization. For a temporary lab deployment, delete in dependency order:
workload runner, Managed Compute deployment, Private Endpoint, Private DNS VNet
links, Private DNS zones, and any lab-only VNet/account. Never delete a
customer-owned VNet. Resource deletion is intentionally not automated by this
repository, and Managed Compute billing continues while the deployment remains.
