#!/usr/bin/env bash
# Step 2 (per GPU VM): managed identity, Azure Monitor Agent, rule and endpoint associations,
# DCGM host engine and the gpumon collector. Runs the in-VM part through Run Command, so no SSH is needed.
#
# Usage: ./onboard-vm.sh -g <vm-resource-group> -n <vm-name> -d <dcr-resource-id> -e <dce-resource-id>
# The VM needs the NVIDIA driver and the DCGM package (datacenter-gpu-manager) installed.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: keep /subscriptions/... arguments unchanged

RG=""; VM=""; DCR_ID=""; DCE_ID=""
while getopts "g:n:d:e:h" opt; do
  case $opt in
    g) RG=$OPTARG ;; n) VM=$OPTARG ;; d) DCR_ID=$OPTARG ;; e) DCE_ID=$OPTARG ;;
    *) sed -n '2,6p' "$0"; exit 1 ;;
  esac
done
[[ -n "$RG" && -n "$VM" && -n "$DCR_ID" && -n "$DCE_ID" ]] || { sed -n '2,6p' "$0"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)

az extension add --upgrade --yes --name monitor-control-service -o none
VM_ID=$(az vm show -g "$RG" -n "$VM" --query id -o tsv)

echo "==> system-assigned managed identity and Azure Monitor Agent"
az vm identity assign -g "$RG" -n "$VM" -o none
az vm extension set -g "$RG" --vm-name "$VM" -n AzureMonitorLinuxAgent --publisher Microsoft.Azure.Monitor \
  --enable-auto-upgrade true -o none

echo "==> associate the data collection rule and endpoint"
az monitor data-collection rule association create --name dcra-gpu-hours --resource "$VM_ID" --rule-id "$DCR_ID" -o none
az monitor data-collection rule association create --name configurationAccessEndpoint --resource "$VM_ID" \
  --endpoint-id "$DCE_ID" -o none

echo "==> DCGM host engine and gpumon collector (Run Command)"
COLLECTOR_B64=$(base64 < "$HERE/../vm/gpu_collector.py" | tr -d '\n')
INSTALLER_B64=$(base64 < "$HERE/../vm/install_collector.sh" | tr -d '\n')
SCRIPT="run-command.$$.sh"  # Run Command runs /bin/sh, so wrap the installer in bash
printf '#!/bin/bash\nexport GPUMON_B64=%s\necho %s | base64 -d > /tmp/install_collector.sh\nbash /tmp/install_collector.sh\n' \
  "$COLLECTOR_B64" "$INSTALLER_B64" > "$SCRIPT"
az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --scripts "@$SCRIPT" --query "value[0].message" -o tsv
rm -f "$SCRIPT"

echo "==> $VM onboarded; the first GpuMetrics_CL rows arrive a few minutes after the agent's first Heartbeat"
