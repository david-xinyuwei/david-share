#!/bin/bash
# ==============================================================================
# GPU Quota Check Script - Run BEFORE azd up
# ==============================================================================
# This script checks GPU quota across Azure regions to help you choose
# the right location for azd up deployment
# ==============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================================================="
echo "   Azure GPU Quota Checker"
echo "=========================================================================="
echo ""
echo "This script will check GPU quota across Azure regions to help you"
echo "choose the right location for your deployment."
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Azure CLI is not installed."
    echo "Install it from: https://learn.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} Not logged in to Azure CLI."
    echo "Please login first:"
    az login
fi

# Get subscription information
echo -e "${BLUE}[INFO]${NC} Getting subscription information..."
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)

echo -e "${GREEN}[SUCCESS]${NC} Using subscription:"
echo "  Name: $SUBSCRIPTION_NAME"
echo "  ID:   $SUBSCRIPTION_ID"
echo ""

# Common GPU regions to check (based on deploymodels script)
REGIONS_TO_CHECK=(
    "eastus"
    "eastus2"
    "westus2"
    "westus3"
    "centralus"
    "northcentralus"
    "southcentralus"
    "westeurope"
    "northeurope"
    "uksouth"
    "japaneast"
    "australiaeast"
    "southeastasia"
    "swedencentral"
    "polandcentral"
)

echo -e "${BLUE}[INFO]${NC} Checking GPU quota for NC-series (A100/H100) in key regions..."
echo ""
echo "This may take 1-2 minutes..."
echo ""

# Results storage
declare -A REGIONS_WITH_QUOTA

# Check each region
for region in "${REGIONS_TO_CHECK[@]}"; do
    # Check for NC-series VMs with A100/H100
    quota_result=$(az vm list-skus \
        --location "$region" \
        --size Standard_NC \
        --all \
        --output json 2>/dev/null | \
        jq -r '.[] | select(.name | contains("A100") or contains("H100")) | select(.restrictions | length == 0) | .name' | \
        head -5)
    
    if [ -n "$quota_result" ]; then
        REGIONS_WITH_QUOTA["$region"]="$quota_result"
        echo -e "${GREEN}✓${NC} $region - GPU available"
    else
        echo -e "${RED}✗${NC} $region - No GPU quota or restricted"
    fi
done

echo ""
echo "=========================================================================="
echo "   GPU Quota Check Results"
echo "=========================================================================="
echo ""

if [ ${#REGIONS_WITH_QUOTA[@]} -eq 0 ]; then
    echo -e "${RED}[ERROR]${NC} No regions found with available GPU quota!"
    echo ""
    echo "Please request GPU quota increase at:"
    echo "https://portal.azure.com/#view/Microsoft_Azure_Support/QuotaMenuBlade/~/myQuotas"
    echo ""
    exit 1
fi

echo -e "${GREEN}Found ${#REGIONS_WITH_QUOTA[@]} region(s) with GPU quota available:${NC}"
echo ""

for region in "${!REGIONS_WITH_QUOTA[@]}"; do
    echo -e "${BLUE}Region:${NC} $region"
    echo "Available SKUs:"
    echo "${REGIONS_WITH_QUOTA[$region]}" | while read -r sku; do
        [ -n "$sku" ] && echo "  • $sku"
    done
    echo ""
done

echo "=========================================================================="
echo ""
echo -e "${YELLOW}Recommended next steps:${NC}"
echo ""
echo "1. Choose one of the regions above that has GPU quota"
echo "2. Run: azd up"
echo "3. When prompted for location, select the region you chose"
echo ""
echo "Example:"
echo "  If you choose 'westus2', select 'westus2' when azd up asks for location"
echo ""
echo "=========================================================================="
echo ""

# Save results to file for later reference
RESULTS_FILE=".gpu-quota-check-results.txt"
cat > "$RESULTS_FILE" <<EOF
GPU Quota Check Results
Date: $(date)
Subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)

Regions with GPU quota:
EOF

for region in "${!REGIONS_WITH_QUOTA[@]}"; do
    echo "" >> "$RESULTS_FILE"
    echo "Region: $region" >> "$RESULTS_FILE"
    echo "${REGIONS_WITH_QUOTA[$region]}" | while read -r sku; do
        [ -n "$sku" ] && echo "  • $sku" >> "$RESULTS_FILE"
    done
done

echo -e "${GREEN}[INFO]${NC} Results saved to: $RESULTS_FILE"
echo ""
