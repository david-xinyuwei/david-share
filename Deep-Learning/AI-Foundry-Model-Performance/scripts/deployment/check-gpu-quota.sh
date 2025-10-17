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
echo "Using parallel execution to speed up checks (max 10 concurrent regions)..."
echo ""

# Results storage
declare -A REGIONS_WITH_QUOTA
declare -A REGIONS_QUOTA_DETAILS

# Create temporary directory for parallel results
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

# Function to check single region (will be called in parallel)
check_region() {
    local region="$1"
    local tmp_dir="$2"
    
    # Check VM quota usage for NC-series in this region
    quota_info=$(az vm list-usage \
        --location "$region" \
        --output json 2>/dev/null | \
        jq -r '.[] | select(.name.value | contains("standardNCADSA100v4Family") or contains("standardNCADSH100v5Family")) | "\(.name.value)|\(.currentValue)|\(.limit)"' 2>/dev/null)
    
    if [ -n "$quota_info" ]; then
        # Parse quota info
        has_available_quota=false
        quota_details=""
        
        while IFS='|' read -r family_name current_value limit; do
            if [ "$limit" -gt 0 ]; then
                available=$((limit - current_value))
                has_available_quota=true
                
                # Translate family name to SKU names
                if [[ "$family_name" == *"A100"* ]]; then
                    sku_type="A100"
                    quota_details+="  • Standard_NC24ads_A100_v4, NC48ads_A100_v4, NC96ads_A100_v4\n"
                elif [[ "$family_name" == *"H100"* ]]; then
                    sku_type="H100"
                    quota_details+="  • Standard_NC40ads_H100_v5, NC80ads_H100_v5\n"
                fi
                quota_details+="    Quota: ${available}/${limit} cores available (${current_value} in use)\n"
            fi
        done <<< "$quota_info"
        
        if [ "$has_available_quota" = true ]; then
            # Save result to temp file
            echo "AVAILABLE|$region|$quota_details" > "$tmp_dir/${region}.result"
        else
            echo "NO_QUOTA|$region" > "$tmp_dir/${region}.result"
        fi
    else
        echo "RESTRICTED|$region" > "$tmp_dir/${region}.result"
    fi
}

# Export function and variables for parallel execution
export -f check_region
export TMP_DIR

# Run checks in parallel (10 concurrent jobs)
printf '%s\n' "${REGIONS_TO_CHECK[@]}" | xargs -P 10 -I {} bash -c 'check_region "$@"' _ {} "$TMP_DIR"

# Collect and display results
echo ""
for region in "${REGIONS_TO_CHECK[@]}"; do
    result_file="$TMP_DIR/${region}.result"
    if [ -f "$result_file" ]; then
        result=$(cat "$result_file")
        status=$(echo "$result" | cut -d'|' -f1)
        region_name=$(echo "$result" | cut -d'|' -f2)
        
        if [ "$status" = "AVAILABLE" ]; then
            quota_details=$(echo "$result" | cut -d'|' -f3-)
            REGIONS_WITH_QUOTA["$region_name"]="available"
            REGIONS_QUOTA_DETAILS["$region_name"]="$quota_details"
            echo -e "${GREEN}✓${NC} $region_name - GPU available"
        elif [ "$status" = "NO_QUOTA" ]; then
            echo -e "${RED}✗${NC} $region_name - No quota available (limit is 0)"
        else
            echo -e "${RED}✗${NC} $region_name - No GPU quota or restricted"
        fi
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
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Region:${NC} $region"
    echo ""
    echo -e "Available GPU SKUs and Quota:"
    echo -e "${REGIONS_QUOTA_DETAILS[$region]}"
done
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

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
    echo -e "${REGIONS_QUOTA_DETAILS[$region]}" >> "$RESULTS_FILE"
done

echo -e "${GREEN}[INFO]${NC} Results saved to: $RESULTS_FILE"
echo ""
