#!/usr/bin/env bash
# Step 2 (per GPU VM): managed identity, Azure Monitor Agent, rule and endpoint associations,
# DCGM host engine and the gpumon collector. Runs the in-VM part through Run Command, so no SSH is needed.
#
# Usage: ./onboard-vm.sh -g <vm-resource-group> -n <vm-name> -d <dcr-resource-id> -e <dce-resource-id>
# The VM needs the NVIDIA driver and the DCGM package (datacenter-gpu-manager) installed.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: keep /subscriptions/... arguments unchanged
az() {
  if [[ -n "${GPUHOURS_SUBSCRIPTION_ID:-}" && "$1" != extension ]]; then
    command az "$@" --subscription "$GPUHOURS_SUBSCRIPTION_ID"
  else
    command az "$@"
  fi
}

RG=""; VM=""; DCR_ID=""; DCE_ID=""
while getopts "g:n:d:e:h" opt; do
  case $opt in
    g) RG=$OPTARG ;; n) VM=$OPTARG ;; d) DCR_ID=$OPTARG ;; e) DCE_ID=$OPTARG ;;
    *) sed -n '2,6p' "$0"; exit 1 ;;
  esac
done
[[ -n "$RG" && -n "$VM" && -n "$DCR_ID" && -n "$DCE_ID" ]] || { sed -n '2,6p' "$0"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)

if [[ "${GPUHOURS_SKIP_CLI_EXTENSION:-0}" != 1 ]]; then  # configure.sh installs it once before parallel runs
  az extension add --upgrade --yes --name monitor-control-service -o none
fi
VM_ID=$(az vm show -g "$RG" -n "$VM" --query id -o tsv)
DCR_NAME=${DCR_ID##*/}
DCR_ASSOC="dcra-$DCR_NAME"

echo "==> system-assigned managed identity and Azure Monitor Agent"
az vm identity assign -g "$RG" -n "$VM" -o none
az vm extension set -g "$RG" --vm-name "$VM" -n AzureMonitorLinuxAgent --publisher Microsoft.Azure.Monitor \
  --enable-auto-upgrade true -o none

echo "==> associate the data collection rule and endpoint"
az monitor data-collection rule association create --name "$DCR_ASSOC" --resource "$VM_ID" --rule-id "$DCR_ID" -o none
EXISTING_DCE=$(az monitor data-collection rule association show --name configurationAccessEndpoint --resource "$VM_ID" \
  --query dataCollectionEndpointId -o tsv 2>/dev/null || true)
if [[ -n "$EXISTING_DCE" && "${EXISTING_DCE,,}" != "${DCE_ID,,}" ]]; then
  echo "ERROR: $VM_ID already uses another configurationAccessEndpoint: $EXISTING_DCE" >&2
  exit 1
fi
if [[ -z "$EXISTING_DCE" ]]; then
  az monitor data-collection rule association create --name configurationAccessEndpoint --resource "$VM_ID" \
    --endpoint-id "$DCE_ID" -o none
fi

echo "==> DCGM host engine and gpumon collector (Run Command)"
COLLECTOR_B64=$(base64 < "$HERE/../vm/gpu_collector.py" | tr -d '\n')
INSTALLER_B64=$(base64 < "$HERE/../vm/install_collector.sh" | tr -d '\n')
SCRIPT="run-command.$$.sh"  # Run Command runs /bin/sh, so wrap the installer in bash
printf '#!/bin/bash\nexport GPUMON_B64=%s\necho %s | base64 -d > /tmp/install_collector.sh\nbash /tmp/install_collector.sh\n' \
  "$COLLECTOR_B64" "$INSTALLER_B64" > "$SCRIPT"
RUN_OUTPUT=$(az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --scripts "@$SCRIPT" \
  --query "value[0].message" -o tsv)
printf '%s\n' "$RUN_OUTPUT"
rm -f "$SCRIPT"
grep -q "active (running)" <<<"$RUN_OUTPUT" || { echo "ERROR: gpumon did not become active" >&2; exit 1; }

echo "==> $VM onboarded; the first GpuMetrics_CL rows arrive a few minutes after the agent's first Heartbeat"
