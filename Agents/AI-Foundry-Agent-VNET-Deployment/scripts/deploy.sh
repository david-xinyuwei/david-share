#!/bin/bash
# deploy.sh — Deploy Azure AI Foundry Agent Service with BYO VNET (E2E Network Isolation)
#
# Usage:
#   ./deploy.sh --region swedencentral --name myagent --resource-group my-rg
#   ./deploy.sh --region koreacentral --name kragent --resource-group kr-rg --model gpt-4o-mini --sku GlobalStandard
#
# Prerequisites:
#   - Azure CLI installed and logged in
#   - Resource providers registered (run with --register-providers first)
#   - Sufficient model quota in target region
#
# Author: Xinyu Wei (Microsoft)

set -e

# Default parameters
REGION="swedencentral"
NAME="foundry"
RG=""
MODEL="gpt-4o"
MODEL_VERSION="2024-11-20"
MODEL_SKU="Standard"
MODEL_CAPACITY=30
VNET_NAME="agent-vnet"
AGENT_SUBNET="agent-subnet"
PE_SUBNET="pe-subnet"
PROJECT_NAME="agentproject"
REGISTER_PROVIDERS=false
TEMPLATE_DIR=""

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --region REGION          Azure region (default: swedencentral)"
    echo "  --name NAME              Short name for resources, lowercase, no hyphens (default: foundry)"
    echo "  --resource-group RG      Resource group name (required)"
    echo "  --model MODEL            Model name (default: gpt-4o)"
    echo "  --model-version VER      Model version (default: 2024-11-20)"
    echo "  --sku SKU                Model SKU: Standard or GlobalStandard (default: Standard)"
    echo "  --capacity CAP           Model capacity in TPM thousands (default: 30)"
    echo "  --vnet-name VNET         VNet name (default: agent-vnet)"
    echo "  --project-name PROJECT   Project name (default: agentproject)"
    echo "  --template-dir DIR       Path to 15-private-network-standard-agent-setup template"
    echo "  --register-providers     Register required resource providers and exit"
    echo "  -h, --help               Show this help"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --region) REGION="$2"; shift 2;;
        --name) NAME="$2"; shift 2;;
        --resource-group) RG="$2"; shift 2;;
        --model) MODEL="$2"; shift 2;;
        --model-version) MODEL_VERSION="$2"; shift 2;;
        --sku) MODEL_SKU="$2"; shift 2;;
        --capacity) MODEL_CAPACITY="$2"; shift 2;;
        --vnet-name) VNET_NAME="$2"; shift 2;;
        --project-name) PROJECT_NAME="$2"; shift 2;;
        --template-dir) TEMPLATE_DIR="$2"; shift 2;;
        --register-providers) REGISTER_PROVIDERS=true; shift;;
        -h|--help) usage;;
        *) echo "Unknown option: $1"; usage;;
    esac
done

# Register providers
if [ "$REGISTER_PROVIDERS" = true ]; then
    echo "=== Registering required resource providers ==="
    for ns in Microsoft.KeyVault Microsoft.CognitiveServices Microsoft.Storage \
              Microsoft.MachineLearningServices Microsoft.Search Microsoft.Network \
              Microsoft.App Microsoft.ContainerService; do
        echo "  Registering $ns..."
        az provider register --namespace "$ns" --wait 2>/dev/null || true
    done
    echo "=== All providers registered ==="
    exit 0
fi

# Validate required params
if [ -z "$RG" ]; then
    echo "ERROR: --resource-group is required"
    usage
fi

if [ -z "$TEMPLATE_DIR" ]; then
    echo "ERROR: --template-dir is required. Clone the official template first:"
    echo "  git clone https://github.com/microsoft-foundry/foundry-samples.git"
    echo "  Then pass: --template-dir foundry-samples/infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup"
    exit 1
fi

# Validate name (no hyphens, max 10 chars to avoid storage name overflow)
if [[ "$NAME" =~ [-] ]] || [ ${#NAME} -gt 10 ]; then
    echo "ERROR: --name must be lowercase, no hyphens, max 10 characters"
    echo "  The template concatenates this into storage account names (max 24 chars)"
    exit 1
fi

# Check quota before deploying
echo "=== Pre-flight: Checking model quota in $REGION ==="
QUOTA_INFO=$(az cognitiveservices usage list --location "$REGION" -o json 2>/dev/null | \
    python3 -c "
import json,sys
data=json.load(sys.stdin)
model='${MODEL}'
sku='${MODEL_SKU}'
capacity=${MODEL_CAPACITY}
found=False
for item in data:
    name=item.get('name',{}).get('value','')
    # Exact match: OpenAI.<SKU>.<model> (not finetune/mini variants)
    expected=f'OpenAI.{sku}.{model}'
    if name == expected:
        cur=item.get('currentValue',0)
        lim=item.get('limit',0)
        avail=lim-cur
        print(f'{name}: {cur}/{lim} (available: {avail})')
        found=True
        if avail < capacity:
            print(f'WARNING: Need {capacity} but only {avail} available!')
            sys.exit(1)
        else:
            print(f'OK: {avail} available, need {capacity}')
if not found:
    print(f'WARNING: Could not find quota for OpenAI.{sku}.{model}')
" 2>&1) || {
    echo "WARNING: Could not verify quota. Proceeding anyway..."
}
echo "$QUOTA_INFO"

# Create resource group
echo "=== Creating resource group: $RG in $REGION ==="
az group create --name "$RG" --location "$REGION" -o table

# Deploy
echo "=== Deploying BYO VNET Agent Service ==="
echo "  Region: $REGION"
echo "  Name: $NAME"
echo "  Model: $MODEL ($MODEL_SKU, capacity $MODEL_CAPACITY)"
echo "  VNet: $VNET_NAME (agent-subnet: 192.168.0.0/24, pe-subnet: 192.168.1.0/24)"
echo ""
echo "  This will take approximately 20-30 minutes..."
echo ""

az deployment group create \
    --resource-group "$RG" \
    --template-file "$TEMPLATE_DIR/main.bicep" \
    --parameters location="$REGION" \
    --parameters aiServices="$NAME" \
    --parameters modelName="$MODEL" \
    --parameters modelFormat='OpenAI' \
    --parameters modelVersion="$MODEL_VERSION" \
    --parameters modelSkuName="$MODEL_SKU" \
    --parameters modelCapacity="$MODEL_CAPACITY" \
    --parameters firstProjectName="$PROJECT_NAME" \
    --parameters displayName="$PROJECT_NAME" \
    --parameters vnetName="$VNET_NAME" \
    --parameters agentSubnetName="$AGENT_SUBNET" \
    --parameters peSubnetName="$PE_SUBNET" \
    -o table

echo ""
echo "=== Deployment complete! ==="
echo ""
echo "Next steps:"
echo "  1. Deploy a jumpbox VM: ./verify.sh --resource-group $RG --vnet-name $VNET_NAME"
echo "  2. Test Agent API from inside VNet: ./test_agent.sh --resource-group $RG --account-name <account>"
echo "  3. Access Foundry Portal via Bastion/VPN (public access is disabled)"
