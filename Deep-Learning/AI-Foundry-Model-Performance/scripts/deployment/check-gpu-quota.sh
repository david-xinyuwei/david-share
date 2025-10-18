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

# Priority regions: Known to support GPU and commonly used
# This list includes regions where A100/H100 are typically available
PRIORITY_REGIONS=(
    # US regions
    "eastus" "eastus2" "westus" "westus2" "westus3"
    "centralus" "northcentralus" "southcentralus"
    # Europe regions
    "westeurope" "northeurope" "francecentral" "uksouth" "ukwest"
    "germanywestcentral" "swedencentral" "norwayeast" "polandcentral"
    "switzerlandnorth" "switzerlandwest" "italynorth" "spaincentral"
    # Asia Pacific
    "japaneast" "japanwest" "koreacentral" "australiaeast" "australiasoutheast"
    "southeastasia" "eastasia" "centralindia" "southindia"
    # Middle East & Africa
    "uaenorth" "qatarcentral" "southafricanorth" "israelcentral"
    # Americas (other)
    "brazilsouth" "canadacentral" "canadaeast"
)

# Add other regions if user wants comprehensive check
echo -e "${YELLOW}[OPTION]${NC} Quick check (recommended regions) or comprehensive check (all regions)?"
echo "  1. Quick - Check ~35 GPU-capable regions (30-60 seconds)"
echo "  2. Comprehensive - Check all 100+ regions (2-5 minutes)"
read -p "Enter choice (1/2, default=1): " CHECK_MODE
CHECK_MODE=${CHECK_MODE:-1}

if [ "$CHECK_MODE" = "2" ]; then
    echo -e "${BLUE}[INFO]${NC} Fetching all available Azure regions..."
    ALL_REGIONS=$(az account list-locations --query "[].name" -o tsv 2>/dev/null)
    
    if [ -z "$ALL_REGIONS" ]; then
        echo -e "${RED}[ERROR]${NC} Failed to fetch regions from Azure"
        exit 1
    fi
    
    # Convert to array
    REGIONS_TO_CHECK=()
    while IFS= read -r region; do
        REGIONS_TO_CHECK+=("$region")
    done <<< "$ALL_REGIONS"
    
    REGION_COUNT=${#REGIONS_TO_CHECK[@]}
    echo -e "${GREEN}[SUCCESS]${NC} Will check all $REGION_COUNT regions"
else
    REGIONS_TO_CHECK=("${PRIORITY_REGIONS[@]}")
    REGION_COUNT=${#REGIONS_TO_CHECK[@]}
    echo -e "${GREEN}[SUCCESS]${NC} Will check $REGION_COUNT priority GPU regions"
fi

echo ""
echo -e "${BLUE}[INFO]${NC} Checking GPU quota for NC-series (A100/H100)..."
echo ""
echo "Using parallel execution to speed up checks (max 15 concurrent regions)..."
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
    
    # Check BOTH VM quota AND ML compute quota for this region
    # First check VM quota (for general VM deployment capability)
    vm_quota_info=$(az vm list-usage \
        --location "$region" \
        --output json 2>/dev/null | \
        jq -r '.[] | select(.name.value | test("Standard(NCADS|NCads)(A100v4|H100v5)Family"; "i")) | "\(.name.value)|\(.currentValue)|\(.limit)"' 2>/dev/null)
    
    # Then check ML compute quota (for AML managed compute - what deploymodels script uses)
    # Note: This requires at least one workspace to exist, otherwise skip ML check
    ml_quota_info=""
    # Try to find any workspace in the subscription to check ML quota
    workspace_info=$(az ml workspace list --output json 2>/dev/null | jq -r '.[0] | "\(.resource_group)|\(.name)"' 2>/dev/null)
    if [ -n "$workspace_info" ]; then
        IFS='|' read -r rg_name ws_name <<< "$workspace_info"
        ml_quota_info=$(az ml compute list-usage \
            --resource-group "$rg_name" \
            --workspace-name "$ws_name" \
            --location "$region" \
            --output json 2>/dev/null | \
            jq -r '.[] | select(.name.value | test("NCADSA100v4|NCADSH100v5"; "i")) | "\(.name.value)|\(.currentValue)|\(.limit)"' 2>/dev/null)
    fi
    
    # Combine results - prioritize ML quota if available, fallback to VM quota
    if [ -n "$ml_quota_info" ]; then
        quota_info="$ml_quota_info"
        quota_source="ML Compute"
    else
        quota_info="$vm_quota_info"
        quota_source="VM"
    fi
    
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
                quota_details+="    Quota Source: ${quota_source}\n"
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

# Run checks in parallel (15 concurrent jobs for faster execution)
printf '%s\n' "${REGIONS_TO_CHECK[@]}" | xargs -P 15 -I {} bash -c 'check_region "$@"' _ {} "$TMP_DIR"

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

# Determine recommended region based on number of regions with quota
REGION_COUNT=${#REGIONS_WITH_QUOTA[@]}
SELECTED_REGION=""

if [ $REGION_COUNT -eq 0 ]; then
    echo -e "${RED}[ERROR]${NC} No GPU quota available. Cannot proceed with deployment."
    echo ""
    exit 1
elif [ $REGION_COUNT -eq 1 ]; then
    # Only one region available - auto-select it
    for region in "${!REGIONS_WITH_QUOTA[@]}"; do
        SELECTED_REGION="$region"
        break
    done
    echo -e "${GREEN}[INFO]${NC} Only one region with GPU quota available: $SELECTED_REGION"
    echo -e "${GREEN}[INFO]${NC} Automatically selected for deployment"
else
    # Multiple regions available - let user choose
    echo -e "${YELLOW}[SELECTION REQUIRED]${NC} Multiple regions have GPU quota available."
    echo ""
    echo "Available regions:"
    
    # Create indexed array of regions
    AVAILABLE_REGIONS=()
    INDEX=1
    for region in "${!REGIONS_WITH_QUOTA[@]}"; do
        AVAILABLE_REGIONS+=("$region")
        echo "  $INDEX. $region"
        INDEX=$((INDEX + 1))
    done
    
    echo ""
    echo -n "Enter the number of your preferred region (1-${#AVAILABLE_REGIONS[@]}): "
    read -r REGION_CHOICE
    
    # Validate input
    if [[ "$REGION_CHOICE" =~ ^[0-9]+$ ]] && [ "$REGION_CHOICE" -ge 1 ] && [ "$REGION_CHOICE" -le "${#AVAILABLE_REGIONS[@]}" ]; then
        SELECTED_REGION="${AVAILABLE_REGIONS[$((REGION_CHOICE - 1))]}"
        echo -e "${GREEN}[INFO]${NC} You selected: $SELECTED_REGION"
    else
        echo -e "${RED}[ERROR]${NC} Invalid selection. Using first region: ${AVAILABLE_REGIONS[0]}"
        SELECTED_REGION="${AVAILABLE_REGIONS[0]}"
    fi
fi

# Save selected region for azd
if [ -n "$SELECTED_REGION" ]; then
    echo "$SELECTED_REGION" > .recommended-region
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Next Step:${NC}"
    echo ""
    echo -e "  Run: ${GREEN}azd up${NC}"
    echo ""
    echo -e "  ✓ Location will be automatically set to: ${GREEN}$SELECTED_REGION${NC}"
    echo -e "  ✓ No manual location selection needed"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
fi

echo "=========================================================================="
echo ""
