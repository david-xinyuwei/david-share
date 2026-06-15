#!/bin/bash
# cleanup.sh — Delete all resources created by deploy.sh and verify.sh
#
# Usage:
#   ./cleanup.sh --resource-group my-rg --account-name myagentXXXX --region swedencentral
#
# IMPORTANT: Must purge Cognitive Services accounts after deletion,
# otherwise the subnet remains locked and cannot be reused.
#
# Author: Xinyu Wei (Microsoft)

set -e

RG=""
ACCOUNT_NAME=""
REGION=""

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --resource-group RG      Resource group name (required)"
    echo "  --account-name NAME      AI Services account name (for purge)"
    echo "  --region REGION          Region (for purge)"
    echo "  -h, --help               Show this help"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --resource-group) RG="$2"; shift 2;;
        --account-name) ACCOUNT_NAME="$2"; shift 2;;
        --region) REGION="$2"; shift 2;;
        -h|--help) usage;;
        *) echo "Unknown option: $1"; usage;;
    esac
done

if [ -z "$RG" ]; then
    echo "ERROR: --resource-group is required"
    usage
fi

echo "=== WARNING: This will delete ALL resources in resource group: $RG ==="
read -p "Are you sure? (y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "=== Deleting resource group: $RG ==="
az group delete --name "$RG" --yes --no-wait
echo "  Resource group deletion initiated (runs in background)"

if [ -n "$ACCOUNT_NAME" ] && [ -n "$REGION" ]; then
    echo ""
    echo "=== Waiting for account deletion before purge (120s) ==="
    sleep 120

    echo "=== Purging Cognitive Services account: $ACCOUNT_NAME ==="
    az cognitiveservices account purge \
        --name "$ACCOUNT_NAME" \
        --resource-group "$RG" \
        --location "$REGION" 2>/dev/null && \
        echo "  Account purged successfully" || \
        echo "  Purge not needed (account already fully deleted)"
fi

echo ""
echo "=== Cleanup complete ==="
echo ""
echo "NOTE: If you encounter 'subnet already in use' errors on next deployment,"
echo "run this to check for lingering deleted accounts:"
echo "  az cognitiveservices account list-deleted -o table"
echo "Then purge them:"
echo "  az cognitiveservices account purge --name <name> --resource-group <rg> --location <region>"
