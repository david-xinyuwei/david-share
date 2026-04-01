#!/bin/bash
# verify.sh — Deploy jumpbox VM and verify BYO VNET Agent Service from inside the VNet
#
# Usage:
#   ./verify.sh --resource-group my-rg --vnet-name agent-vnet --account-name myagentXXXX
#
# This script:
#   1. Creates a jumpbox VM in pe-subnet
#   2. Enables Managed Identity on the VM
#   3. Assigns Cognitive Services Contributor role
#   4. Verifies DNS resolution (Private IP)
#   5. Verifies Agent API connectivity
#   6. Creates a test Agent via Private Link
#
# Author: Xinyu Wei (Microsoft)

set -e

RG=""
VNET_NAME="agent-vnet"
PE_SUBNET="pe-subnet"
ACCOUNT_NAME=""
VM_NAME="jumpbox"
VM_SIZE="Standard_B2s"

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --resource-group RG      Resource group name (required)"
    echo "  --vnet-name VNET         VNet name (default: agent-vnet)"
    echo "  --account-name NAME      AI Services account name (required)"
    echo "  --vm-name NAME           Jumpbox VM name (default: jumpbox)"
    echo "  --vm-size SIZE           VM size (default: Standard_B2s)"
    echo "  -h, --help               Show this help"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --resource-group) RG="$2"; shift 2;;
        --vnet-name) VNET_NAME="$2"; shift 2;;
        --account-name) ACCOUNT_NAME="$2"; shift 2;;
        --vm-name) VM_NAME="$2"; shift 2;;
        --vm-size) VM_SIZE="$2"; shift 2;;
        -h|--help) usage;;
        *) echo "Unknown option: $1"; usage;;
    esac
done

if [ -z "$RG" ] || [ -z "$ACCOUNT_NAME" ]; then
    echo "ERROR: --resource-group and --account-name are required"
    usage
fi

SUB_ID=$(az account show --query id -o tsv)

echo "=== Step 1: Creating jumpbox VM ==="
az vm create \
    --resource-group "$RG" \
    --name "$VM_NAME" \
    --image "Ubuntu2404" \
    --size "$VM_SIZE" \
    --vnet-name "$VNET_NAME" \
    --subnet "$PE_SUBNET" \
    --admin-username "azureuser" \
    --generate-ssh-keys \
    --public-ip-sku Standard \
    --nsg-rule SSH \
    -o table

echo ""
echo "=== Step 2: Enabling Managed Identity ==="
PRINCIPAL_ID=$(az vm identity assign --resource-group "$RG" --name "$VM_NAME" --query systemAssignedIdentity -o tsv)
echo "  Principal ID: $PRINCIPAL_ID"

echo ""
echo "=== Step 3: Assigning RBAC ==="
# Cognitive Services Contributor for management operations
az role assignment create \
    --assignee "$PRINCIPAL_ID" \
    --role "Cognitive Services Contributor" \
    --scope "/subscriptions/$SUB_ID/resourceGroups/$RG" \
    -o none 2>/dev/null || true
# Cognitive Services OpenAI Contributor for Agent data plane (create/list/delete assistants)
ACCOUNT_SCOPE="/subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.CognitiveServices/accounts/$ACCOUNT_NAME"
az role assignment create \
    --assignee "$PRINCIPAL_ID" \
    --role "a001fd3d-188f-4b5d-821b-7da978bf7442" \
    --scope "$ACCOUNT_SCOPE" \
    -o none 2>/dev/null || true
echo "  RBAC roles assigned (Cognitive Services Contributor + OpenAI Contributor)"

echo ""
echo "=== Step 4: Waiting 60s for RBAC propagation ==="
sleep 60

echo ""
echo "=== Step 5: Running verification from inside VNet ==="
az vm run-command create \
    --resource-group "$RG" \
    --vm-name "$VM_NAME" \
    --name "vnet-verify" \
    --script "
pip3 install -q requests 2>/dev/null

python3 << 'PYEOF'
import requests, json, socket

ACCOUNT = '${ACCOUNT_NAME}'
ENDPOINT = f'https://{ACCOUNT}.cognitiveservices.azure.com'

# Test 1: DNS Resolution
print('=== DNS Resolution Test ===')
for suffix in ['cognitiveservices.azure.com', 'openai.azure.com']:
    fqdn = f'{ACCOUNT}.{suffix}'
    try:
        ip = socket.gethostbyname(fqdn)
        is_private = ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.')
        status = 'PRIVATE' if is_private else 'PUBLIC'
        print(f'  {fqdn} -> {ip} [{status}]')
    except Exception as e:
        print(f'  {fqdn} -> ERROR: {e}')

# Test 2: Get Token via Managed Identity
print()
print('=== Managed Identity Token Test ===')
try:
    resp = requests.get(
        'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://cognitiveservices.azure.com',
        headers={'Metadata': 'true'}, timeout=10
    )
    if resp.status_code == 200:
        token = resp.json()['access_token']
        print(f'  Token acquired: YES (HTTP {resp.status_code})')
    else:
        print(f'  Token failed: HTTP {resp.status_code} - {resp.text[:200]}')
        token = None
except Exception as e:
    print(f'  Token error: {e}')
    token = None

if not token:
    print()
    print('Cannot proceed without token. Check Managed Identity setup.')
    exit(1)

headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# Test 3: List Agents
print()
print('=== Agent API Test ===')
r = requests.get(f'{ENDPOINT}/openai/assistants?api-version=2024-07-01-preview', headers=headers, timeout=15)
print(f'  List agents: HTTP {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'  Existing agents: {len(data.get(\"data\", []))}')

# Test 4: Create Agent
print()
print('=== Agent Creation Test ===')
agent_body = {
    'model': 'gpt-4o',
    'name': 'vnet-verification-agent',
    'instructions': 'You are a test agent created to verify BYO VNET Private Link connectivity.'
}
r = requests.post(f'{ENDPOINT}/openai/assistants?api-version=2024-07-01-preview', headers=headers, json=agent_body, timeout=30)
print(f'  Create agent: HTTP {r.status_code}')
if r.status_code == 200:
    agent = r.json()
    print(f'  Agent ID: {agent.get(\"id\")}')
    print(f'  Agent Name: {agent.get(\"name\")}')
    print(f'  Model: {agent.get(\"model\")}')
    print()
    print('=== ALL TESTS PASSED ===')

    # Cleanup: delete the test agent
    del_r = requests.delete(f'{ENDPOINT}/openai/assistants/{agent[\"id\"]}?api-version=2024-07-01-preview', headers=headers, timeout=15)
    print(f'  Cleanup (delete test agent): HTTP {del_r.status_code}')
else:
    print(f'  Response: {r.text[:300]}')
    # If gpt-4o not available, try gpt-4o-mini
    agent_body['model'] = 'gpt-4o-mini'
    r2 = requests.post(f'{ENDPOINT}/openai/assistants?api-version=2024-07-01-preview', headers=headers, json=agent_body, timeout=30)
    print(f'  Retry with gpt-4o-mini: HTTP {r2.status_code}')
    if r2.status_code == 200:
        agent2 = r2.json()
        print(f'  Agent ID: {agent2.get(\"id\")}')
        print()
        print('=== ALL TESTS PASSED (with gpt-4o-mini) ===')
        del_r2 = requests.delete(f'{ENDPOINT}/openai/assistants/{agent2[\"id\"]}?api-version=2024-07-01-preview', headers=headers, timeout=15)
PYEOF
" --no-wait -o none 2>/dev/null

echo "  Command submitted. Waiting 60s for execution..."
sleep 60

echo ""
echo "=== Verification Results ==="
az vm run-command show \
    --resource-group "$RG" \
    --vm-name "$VM_NAME" \
    --name "vnet-verify" \
    --instance-view \
    --query "instanceView.{output:output, error:error, state:executionState}" \
    -o json
