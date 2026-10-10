#!/usr/bin/env bash
# Deploy (or update) the Azure Monitor workbook next to the Log Analytics workspace, or remove it with -d.
#
# Usage: ./deploy-workbook.sh -g <workspace-rg> [-w <workspace-name>] [-n <display-name>] [-d]
# The workbook is azure/workbook.json, built from kql/ and azure/workbook/ by tools/build_workbook.py.
# Its resource name is derived from the workspace ID, so a rerun updates the same workbook.
# Needs: Contributor (or Workbook Contributor) on the resource group. Viewers need Log Analytics Reader.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: keep /subscriptions/... arguments unchanged
az() {
  if [[ -n "${GPUHOURS_SUBSCRIPTION_ID:-}" && "$1" != extension ]]; then
    command az "$@" --subscription "$GPUHOURS_SUBSCRIPTION_ID"
  else
    command az "$@"
  fi
}
clean() { tr -d '\r'; }

RG=""; LAW="law-gpu-hours"; NAME="GPU 卡时统计（DCGM + Azure Monitor）"; DELETE=0
while getopts "g:w:n:dh" opt; do
  case $opt in
    g) RG=$OPTARG ;; w) LAW=$OPTARG ;; n) NAME=$OPTARG ;; d) DELETE=1 ;;
    *) sed -n '2,7p' "$0"; exit 1 ;;
  esac
done
[[ -n "$RG" ]] || { sed -n '2,7p' "$0"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
TEMPLATE="$HERE/../azure/workbook.json"
# Git Bash on Windows: the Windows az needs C:/... instead of /c/...
if command -v cygpath >/dev/null; then TEMPLATE=$(cygpath -m "$TEMPLATE"); fi

LAW_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query id -o tsv | clean)
[[ -n "$LAW_ID" ]] || { echo "ERROR: workspace $LAW not found in $RG" >&2; exit 1; }

if [[ "$DELETE" == 1 ]]; then
  IDS=$(az resource list -g "$RG" --resource-type Microsoft.Insights/workbooks \
    --query "[?tolower(properties.sourceId)=='${LAW_ID,,}'].id" -o tsv | clean)
  for id in $IDS; do az resource delete --ids "$id" -o none; echo "deleted $id"; done
  [[ -n "$IDS" ]] || echo "no workbook for $LAW in $RG"
  exit 0
fi

echo "==> workbook for $LAW_ID"
DEPLOY="gpu-hours-workbook-$(printf '%s' "$LAW_ID" | cksum | cut -d' ' -f1)"
WORKBOOK_ID=$(az deployment group create -g "$RG" -n "$DEPLOY" --template-file "$TEMPLATE" \
  --parameters workspaceResourceId="$LAW_ID" displayName="$NAME" \
  --query properties.outputs.workbookId.value -o tsv | clean)
[[ -n "$WORKBOOK_ID" ]] || { echo "ERROR: deployment returned no workbook ID" >&2; exit 1; }
TENANT_ID=$(az account show --query tenantId -o tsv | clean)
echo "workbook deployed: $WORKBOOK_ID"
echo "open: https://portal.azure.com/#@$TENANT_ID/resource$WORKBOOK_ID/workbook"
