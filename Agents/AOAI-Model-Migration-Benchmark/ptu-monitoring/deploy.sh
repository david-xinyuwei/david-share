#!/bin/bash
# ============================================================
# Deploy PTU Monitoring: Azure Monitor + APIM + Alert Rules
# ============================================================
# Usage:
#   ./deploy.sh \
#     --resource-group rg-lenovo-qira \
#     --aoai-name my-aoai-resource \
#     --ptu-endpoint https://xxx.openai.azure.com \
#     --paygo-endpoint https://yyy.openai.azure.com \
#     --email ops-team@company.com

set -euo pipefail

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --resource-group) RG="$2"; shift 2 ;;
    --aoai-name) AOAI_NAME="$2"; shift 2 ;;
    --ptu-endpoint) PTU_EP="$2"; shift 2 ;;
    --paygo-endpoint) PAYGO_EP="$2"; shift 2 ;;
    --email) EMAIL="$2"; shift 2 ;;
    --location) LOCATION="$2"; shift 2 ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

LOCATION="${LOCATION:-eastus2}"

echo "============================================"
echo "  PTU Monitoring Deployment"
echo "============================================"
echo "  Resource Group:  $RG"
echo "  AOAI Resource:   $AOAI_NAME"
echo "  PTU Endpoint:    $PTU_EP"
echo "  PAYGO Endpoint:  $PAYGO_EP"
echo "  Alert Email:     $EMAIL"
echo "  Location:        $LOCATION"
echo "============================================"
echo ""

# Step 1: Deploy Bicep (Log Analytics + Diagnostics + Alerts + APIM)
echo ">>> Step 1: Deploying infrastructure (Bicep)..."
az deployment group create \
  --resource-group "$RG" \
  --template-file "$(dirname "$0")/infra/ptu-monitoring.bicep" \
  --parameters \
    aoaiResourceName="$AOAI_NAME" \
    ptuEndpoint="$PTU_EP" \
    paygoEndpoint="$PAYGO_EP" \
    actionGroupEmail="$EMAIL" \
    location="$LOCATION" \
  --output table

APIM_NAME=$(az deployment group show \
  --resource-group "$RG" \
  --name ptu-monitoring \
  --query "properties.outputs.apimName.value" -o tsv 2>/dev/null || echo "")

echo ""
echo ">>> Step 2: Apply APIM routing policy..."
if [ -n "$APIM_NAME" ]; then
  echo "  APIM: $APIM_NAME"
  echo "  NOTE: Apply apim-policy-ptu-routing.xml to your API in Azure Portal:"
  echo "    APIM → APIs → Your API → All operations → Inbound/Outbound processing → Code editor"
  echo "    Paste the contents of ptu-monitoring/apim-policy-ptu-routing.xml"
else
  echo "  APIM name not found in deployment output. Apply policy manually."
fi

echo ""
echo ">>> Step 3: Verify deployment..."
echo "  Diagnostic Settings:"
az monitor diagnostic-settings show \
  --name ptu-diagnostics \
  --resource "$AOAI_NAME" \
  --resource-group "$RG" \
  --resource-type "Microsoft.CognitiveServices/accounts" \
  --query "{name:name, workspace:workspaceId}" -o table 2>/dev/null || echo "  (verify manually in Portal)"

echo ""
echo "  Alert Rules:"
az monitor metrics alert list \
  --resource-group "$RG" \
  --query "[?contains(name,'ptu')].{name:name, severity:severity, enabled:enabled}" \
  -o table 2>/dev/null || echo "  (verify manually in Portal)"

echo ""
echo "============================================"
echo "  Deployment complete!"
echo ""
echo "  Next steps:"
echo "  1. Apply APIM policy (apim-policy-ptu-routing.xml)"
echo "  2. Verify alerts in Portal → Monitor → Alerts"
echo "  3. Check PTU Utilization dashboard in AOAI resource"
echo "  4. Run stress test to validate:"
echo "     python scripts/stress_test_tpm_utilization.py \\"
echo "       --endpoint $PTU_EP --api-key <key> --concurrency 50 --total 300"
echo "============================================"
