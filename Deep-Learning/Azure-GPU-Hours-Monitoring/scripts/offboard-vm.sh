#!/usr/bin/env bash
# Remove GPU-hours monitoring from one VM (collector, AMA extension, DCR/DCE associations).
# Leaves the NVIDIA driver, DCGM package and the VM's managed identity in place.
#
# Usage: ./offboard-vm.sh -g <vm-resource-group> -n <vm-name>
set -euo pipefail

RG=""; VM=""
while getopts "g:n:h" opt; do
  case $opt in g) RG=$OPTARG ;; n) VM=$OPTARG ;; h|*) sed -n '2,6p' "$0"; exit 0 ;; esac
done
[[ -z "$RG" || -z "$VM" ]] && { echo "usage: $0 -g <rg> -n <vm>"; exit 1; }

VM_ID=$(az vm show -g "$RG" -n "$VM" --query id -o tsv)
API="api-version=2023-03-11"

echo "==> stop and remove gpumon collector"
az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --scripts \
  "systemctl disable --now gpumon 2>/dev/null; rm -rf /opt/gpumon /var/log/gpumon /etc/systemd/system/gpumon.service; systemctl daemon-reload; echo removed" \
  --query "value[0].message" -o tsv

echo "==> remove DCR / DCE associations"
az rest --method delete --url "https://management.azure.com${VM_ID}/providers/Microsoft.Insights/dataCollectionRuleAssociations/dcra-gpuhours?$API" -o none || true
az rest --method delete --url "https://management.azure.com${VM_ID}/providers/Microsoft.Insights/dataCollectionRuleAssociations/configurationAccessEndpoint?$API" -o none || true

echo "==> remove Azure Monitor Agent"
az vm extension delete -g "$RG" --vm-name "$VM" -n AzureMonitorLinuxAgent -o none || true

echo "==> $VM offboarded"
