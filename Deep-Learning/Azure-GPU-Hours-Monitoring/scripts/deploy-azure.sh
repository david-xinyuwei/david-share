#!/usr/bin/env bash
# Deploy the Azure side of GPU-hours monitoring (run once per Log Analytics workspace).
#
#   Log Analytics workspace + GpuMetrics_CL table
#   Data Collection Endpoint + Data Collection Rule (Custom JSON Logs -> GpuMetrics_CL)
#   Workbook (dashboard) + idle-GPU alert rule
#
# Usage:
#   ./deploy-azure.sh -g <resource-group> -l <location> [-w <workspace-name>] [-r <retention-days>]
#
# Requires: az CLI (logged in, correct subscription selected), python3.
set -euo pipefail

RG=""; LOC=""; LAW="law-gpuhours"; RETENTION=90
while getopts "g:l:w:r:h" opt; do
  case $opt in
    g) RG=$OPTARG ;; l) LOC=$OPTARG ;; w) LAW=$OPTARG ;; r) RETENTION=$OPTARG ;;
    h|*) sed -n '2,12p' "$0"; exit 0 ;;
  esac
done
[[ -z "$RG" || -z "$LOC" ]] && { echo "usage: $0 -g <rg> -l <location> [-w law-name] [-r retention-days]"; exit 1; }

HERE=$(cd "$(dirname "$0")" && pwd)
AZ_DIR="$HERE/../azure"
SUB=$(az account show --query id -o tsv)
echo "==> subscription $SUB, resource group $RG ($LOC), workspace $LAW, retention ${RETENTION}d"

az group create -n "$RG" -l "$LOC" --tags purpose=gpu-hours-monitoring -o none

echo "==> Log Analytics workspace"
az monitor log-analytics workspace create -g "$RG" -n "$LAW" -l "$LOC" --retention-time "$RETENTION" -o none

echo "==> GpuMetrics_CL table"
az monitor log-analytics workspace table create -g "$RG" --workspace-name "$LAW" -n GpuMetrics_CL \
  --retention-time "$RETENTION" \
  --columns TimeGenerated=datetime Computer=string FilePath=string VmName=string VmSize=string \
            VmResourceId=string Tags=string GpuId=int GpuUuid=string GpuName=string Samples=int \
            GpuUtil=real GrActive=real SmActive=real TensorActive=real DramActive=real \
            FbUsedMiB=real FbTotalMiB=real PowerW=real TempC=real ProcCount=int Users=string Processes=string \
  -o none

echo "==> DCE + DCR"
az deployment group create -g "$RG" -n gpuhours-dcr --template-file "$AZ_DIR/dcr.json" \
  --parameters workspaceName="$LAW" dceName="dce-gpuhours" dcrName="dcr-gpuhours" -o none

echo "==> Workbook + alert"
python3 "$AZ_DIR/build_workbook.py" >/dev/null
az deployment group create -g "$RG" -n gpuhours-workbook --template-file "$AZ_DIR/workbook.json" \
  --parameters "@$AZ_DIR/workbook.parameters.json" workspaceName="$LAW" -o none

WS_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query customerId -o tsv)
DCR_ID="/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Insights/dataCollectionRules/dcr-gpuhours"
DCE_ID="/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Insights/dataCollectionEndpoints/dce-gpuhours"

cat <<EOF

==> Done. Save these for onboard-vm.sh and deploy-webui.sh:

  WORKSPACE_ID=$WS_ID
  DCR_ID=$DCR_ID
  DCE_ID=$DCE_ID

Next:
  ./onboard-vm.sh -g <vm-rg> -n <vm-name> -d "$DCR_ID" -e "$DCE_ID"
  ./deploy-webui.sh -g $RG -n <unique-webapp-name> -w $WS_ID -l <location>
EOF
