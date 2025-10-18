#!/bin/bash
# ==============================================================================
# Smart GPU Quota Scanner - Finds ALL regions with A100/H100 quota
# ==============================================================================
# This script quickly scans all Azure regions and shows ONLY regions with quota
# Optimized for speed with parallel processing and timeouts
# ==============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "=========================================================================="
echo "   Smart GPU Quota Scanner - Find Your A100/H100 Regions"
echo "=========================================================================="
echo ""

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Azure CLI not installed"
    echo "Install from: https://learn.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Check login
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} Not logged in to Azure"
    az login
fi

# Get subscription
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)

echo -e "${GREEN}✓${NC} Subscription: ${CYAN}$SUBSCRIPTION_NAME${NC}"
echo "  ID: $SUBSCRIPTION_ID"
echo ""

# Get all regions
echo -e "${BLUE}[1/3]${NC} Fetching all Azure regions..."
ALL_REGIONS=$(az account list-locations --query "[].name" -o tsv 2>/dev/null)

if [ -z "$ALL_REGIONS" ]; then
    echo -e "${RED}[ERROR]${NC} Failed to get regions"
    exit 1
fi

# Convert to array
REGIONS_TO_CHECK=()
while IFS= read -r region; do
    REGIONS_TO_CHECK+=("$region")
done <<< "$ALL_REGIONS"

TOTAL_REGIONS=${#REGIONS_TO_CHECK[@]}
echo -e "${GREEN}✓${NC} Found $TOTAL_REGIONS regions to scan"
echo ""

echo -e "${BLUE}[2/3]${NC} Scanning for GPU quota (A100/H100)..."
echo "  Strategy: 30 parallel checks with 10s timeout per region"
echo "  Time: ~60-90 seconds"
echo ""

# Temporary file for results
RESULTS_FILE=$(mktemp)
trap "rm -f $RESULTS_FILE" EXIT

# Check function with timeout
check_region() {
    local region=$1
    local subscription=$2
    
    # 10-second timeout for fast scanning
    quota=$(timeout 10s az ml compute list-usage \
        --location "$region" \
        --subscription "$subscription" \
        2>/dev/null | grep -E "Standard_NC|Standard_ND" || true)
    
    if [ -z "$quota" ]; then
        return  # No GPU quota, skip silently
    fi
    
    # Parse A100 quota
    a100_24=$(echo "$quota" | grep "Standard_NC24ads_A100_v4" | grep -oP '"currentValue":\K[0-9]+' || echo "0")
    a100_48=$(echo "$quota" | grep "Standard_NC48ads_A100_v4" | grep -oP '"currentValue":\K[0-9]+' || echo "0")
    a100_96=$(echo "$quota" | grep "Standard_NC96ads_A100_v4" | grep -oP '"currentValue":\K[0-9]+' || echo "0")
    nd96asr=$(echo "$quota" | grep "Standard_ND96asr_v4" | grep -oP '"currentValue":\K[0-9]+' || echo "0")
    nd96amsr=$(echo "$quota" | grep "Standard_ND96amsr_A100_v4" | grep -oP '"currentValue":\K[0-9]+' || echo "0")
    
    # Parse H100 quota
    h100_40=$(echo "$quota" | grep "Standard_NC40ads_H100_v5" | grep -oP '"currentValue":\K[0-9]+' || echo "0")
    h100_80=$(echo "$quota" | grep -E "Standard_NC80ads_H100_v5|Standard_NC80adis_H100_v5" | grep -oP '"currentValue":\K[0-9]+' || echo "0")
    nd96isr=$(echo "$quota" | grep "Standard_ND96isr_H100_v5" | grep -oP '"currentValue":\K[0-9]+' || echo "0")
    
    # Calculate totals
    total_a100=$((a100_24 + a100_48 + a100_96 + nd96asr + nd96amsr))
    total_h100=$((h100_40 + h100_80 + nd96isr))
    
    # Only report if has quota
    if [ $total_a100 -gt 0 ] || [ $total_h100 -gt 0 ]; then
        echo "$region|$total_a100|$total_h100|$a100_24|$a100_48|$a100_96|$h100_40|$h100_80" >> "$RESULTS_FILE"
    fi
}

# Parallel execution
MAX_PARALLEL=30
active_jobs=0
checked=0

for region in "${REGIONS_TO_CHECK[@]}"; do
    check_region "$region" "$SUBSCRIPTION_ID" &
    ((active_jobs++))
    ((checked++))
    
    # Progress indicator (every 20 regions)
    if [ $((checked % 20)) -eq 0 ]; then
        percent=$((checked * 100 / TOTAL_REGIONS))
        echo -e "${BLUE}  Progress:${NC} $checked/$TOTAL_REGIONS regions ($percent%)"
    fi
    
    # Limit concurrency
    if [ $active_jobs -ge $MAX_PARALLEL ]; then
        wait -n 2>/dev/null || true
        ((active_jobs--))
    fi
done

# Wait for all remaining jobs
wait

echo -e "${BLUE}  Progress:${NC} $TOTAL_REGIONS/$TOTAL_REGIONS regions (100%)"
echo ""

# Display results
echo -e "${BLUE}[3/3]${NC} Results - Regions with GPU quota:"
echo "=========================================================================="

if [ ! -s "$RESULTS_FILE" ]; then
    echo -e "${YELLOW}⚠️  No GPU quota found in any region${NC}"
    echo ""
    echo "Possible reasons:"
    echo "  1. No GPU quota allocated to this subscription"
    echo "  2. Need to request quota in Azure Portal"
    echo "  3. Check different subscription"
    exit 0
fi

# Sort by total quota (A100 + H100) descending
sort -t'|' -k2,3 -nr "$RESULTS_FILE" | while IFS='|' read -r region a100_total h100_total a100_24 a100_48 a100_96 h100_40 h100_80; do
    echo ""
    echo -e "${GREEN}✓ ${CYAN}$region${NC}"
    
    if [ $a100_total -gt 0 ]; then
        echo -e "  ${YELLOW}A100:${NC} $a100_total cores total"
        [ $a100_24 -gt 0 ] && echo "    • NC24ads (24 cores):  $a100_24 cores"
        [ $a100_48 -gt 0 ] && echo "    • NC48ads (48 cores):  $a100_48 cores"
        [ $a100_96 -gt 0 ] && echo "    • NC96ads (96 cores):  $a100_96 cores"
    fi
    
    if [ $h100_total -gt 0 ]; then
        echo -e "  ${YELLOW}H100:${NC} $h100_total cores total"
        [ $h100_40 -gt 0 ] && echo "    • NC40ads (40 cores):  $h100_40 cores"
        [ $h100_80 -gt 0 ] && echo "    • NC80ads (80 cores):  $h100_80 cores"
    fi
done

echo ""
echo "=========================================================================="
echo -e "${GREEN}✓ Scan complete${NC}"
echo ""
echo "💡 TIP: Use these regions when running deploymodels script"
echo "    Example: Select one of the regions above as your deployment location"
echo ""
