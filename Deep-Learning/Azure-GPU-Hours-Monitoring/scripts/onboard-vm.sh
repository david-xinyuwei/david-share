#!/usr/bin/env bash
# Onboard one GPU VM to GPU-hours monitoring (repeat per VM, or drive from a loop / Azure Policy).
#
#   1. system-assigned managed identity (AMA needs it to authenticate)
#   2. AzureMonitorLinuxAgent extension
#   3. DCR + DCE association
#   4. DCGM host engine + gpumon collector service (via Run Command; no SSH required)
#
# Usage:
#   ./onboard-vm.sh -g <vm-resource-group> -n <vm-name> -d <dcr-resource-id> -e <dce-resource-id>
#
# The VM must already have the NVIDIA driver and datacenter-gpu-manager installed
# (the Azure HPC / ubuntu-hpc images and NvidiaGpuDriverLinux extension satisfy this).
set -euo pipefail

RG=""; VM=""; DCR=""; DCE=""
while getopts "g:n:d:e:h" opt; do
  case $opt in
    g) RG=$OPTARG ;; n) VM=$OPTARG ;; d) DCR=$OPTARG ;; e) DCE=$OPTARG ;;
    h|*) sed -n '2,13p' "$0"; exit 0 ;;
  esac
done
[[ -z "$RG" || -z "$VM" || -z "$DCR" || -z "$DCE" ]] && { echo "usage: $0 -g <rg> -n <vm> -d <dcr-id> -e <dce-id>"; exit 1; }

HERE=$(cd "$(dirname "$0")" && pwd)
VM_DIR="$HERE/../vm"
VM_ID=$(az vm show -g "$RG" -n "$VM" --query id -o tsv)
echo "==> $VM_ID"

echo "==> managed identity + Azure Monitor Agent"
az vm identity assign -g "$RG" -n "$VM" -o none
az vm extension set -g "$RG" --vm-name "$VM" -n AzureMonitorLinuxAgent \
  --publisher Microsoft.Azure.Monitor --enable-auto-upgrade true -o none

echo "==> DCR / DCE associations"
API="api-version=2023-03-11"
az rest --method put --url "https://management.azure.com${VM_ID}/providers/Microsoft.Insights/dataCollectionRuleAssociations/dcra-gpuhours?$API" \
  --body "{\"properties\":{\"dataCollectionRuleId\":\"$DCR\"}}" -o none
az rest --method put --url "https://management.azure.com${VM_ID}/providers/Microsoft.Insights/dataCollectionRuleAssociations/configurationAccessEndpoint?$API" \
  --body "{\"properties\":{\"dataCollectionEndpointId\":\"$DCE\"}}" -o none

echo "==> DCGM + gpumon collector (Run Command)"
# Run Command executes with /bin/sh, so wrap in bash and ship both files base64-encoded.
COLLECTOR_B64=$(base64 -w0 < "$VM_DIR/gpu_collector.py")
INSTALL_B64=$(base64 -w0 < "$VM_DIR/install_collector.sh")
TMP=$(mktemp)
cat > "$TMP" <<EOF
#!/bin/bash
export GPUMON_B64='$COLLECTOR_B64'
echo '$INSTALL_B64' | base64 -d > /tmp/install_collector.sh
bash /tmp/install_collector.sh
EOF
az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --scripts "@$TMP" \
  --query "value[0].message" -o tsv
rm -f "$TMP"

cat <<EOF

==> $VM onboarded. First GpuMetrics_CL rows appear in ~3-5 minutes. Verify with:
  GpuMetrics_CL | where Computer == "$VM" | top 5 by TimeGenerated
EOF
