#!/usr/bin/env bash
# Step 1 (once per workspace): Log Analytics workspace, GpuMetrics_CL table, data collection endpoint and rule.
#
# Usage: ./setup-workspace.sh -g <resource-group> -l <region> [-w <workspace-name>] [-r <retention-days>]
#        [-a <aml-workspace-resource-id>]
# Needs: Azure CLI logged in (az login) with Contributor on the resource group. Job tracking also
# needs permission to create subscription diagnostic settings and AML workspace diagnostic settings.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: keep /subscriptions/... arguments unchanged

RG=""; LOC=""; LAW="law-gpu-hours"; RETENTION=90; AML_ID=""
while getopts "g:l:w:r:a:h" opt; do
  case $opt in
    g) RG=$OPTARG ;; l) LOC=$OPTARG ;; w) LAW=$OPTARG ;; r) RETENTION=$OPTARG ;;
    a) AML_ID=$OPTARG ;;
    *) sed -n '2,5p' "$0"; exit 1 ;;
  esac
done
[[ -n "$RG" && -n "$LOC" ]] || { sed -n '2,5p' "$0"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
DCE="dce-gpu-hours"; DCR="dcr-gpu-hours"

az extension add --upgrade --yes --name monitor-control-service -o none

echo "==> resource group and Log Analytics workspace"
az group create -n "$RG" -l "$LOC" -o none
az monitor log-analytics workspace create -g "$RG" -n "$LAW" -l "$LOC" --retention-time "$RETENTION" -o none

echo "==> GpuMetrics_CL table"
COLUMNS=(TimeGenerated=datetime Computer=string FilePath=string VmName=string VmSize=string VmResourceId=string
         Tags=string GpuId=int GpuUuid=string GpuName=string Samples=int GpuUtil=real GrActive=real SmActive=real
         TensorActive=real DramActive=real FbUsedMiB=real FbTotalMiB=real PowerW=real TempC=real ProcCount=int
         Users=string Processes=string RunId=string)
if az monitor log-analytics workspace table show -g "$RG" --workspace-name "$LAW" -n GpuMetrics_CL -o none 2>/dev/null; then
  az monitor log-analytics workspace table update -g "$RG" --workspace-name "$LAW" -n GpuMetrics_CL \
    --retention-time "$RETENTION" --columns "${COLUMNS[@]}" -o none
else
  az monitor log-analytics workspace table create -g "$RG" --workspace-name "$LAW" -n GpuMetrics_CL \
    --retention-time "$RETENTION" --columns "${COLUMNS[@]}" -o none
fi

echo "==> data collection endpoint and rule"
az monitor data-collection endpoint create -g "$RG" -n "$DCE" -l "$LOC" --public-network-access Enabled -o none
LAW_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query id -o tsv)
DCE_ID=$(az monitor data-collection endpoint show -g "$RG" -n "$DCE" --query id -o tsv)
RULE_FILE="dcr-rule.$$.json"  # relative path: readable by the Windows and the Linux Azure CLI alike
sed "s#__WORKSPACE_RESOURCE_ID__#${LAW_ID}#" "$HERE/../azure/dcr-rule.json" > "$RULE_FILE"
az monitor data-collection rule create -g "$RG" -n "$DCR" -l "$LOC" --kind Linux \
  --endpoint-id "$DCE_ID" --rule-file "$RULE_FILE" -o none
rm -f "$RULE_FILE"
DCR_ID=$(az monitor data-collection rule show -g "$RG" -n "$DCR" --query id -o tsv)
WORKSPACE_GUID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query customerId -o tsv)

if [[ -n "$AML_ID" ]]; then
  echo "==> job submitter and status diagnostics"
  az monitor diagnostic-settings subscription create -n gpu-hours-job-submitters -l "$LOC" \
    --workspace "$LAW_ID" --logs '[{"category":"Administrative","enabled":true}]' -o none
  az monitor diagnostic-settings create -n gpu-hours-job-status --resource "$AML_ID" --workspace "$LAW_ID" \
    --export-to-resource-specific true --logs '[{"category":"AmlRunStatusChangedEvent","enabled":true}]' -o none
fi

cat <<EOF
==> done
WORKSPACE_GUID=$WORKSPACE_GUID
DCR_ID=$DCR_ID
DCE_ID=$DCE_ID
JOB_TRACKING=$([[ -n "$AML_ID" ]] && echo enabled || echo disabled)
EOF
