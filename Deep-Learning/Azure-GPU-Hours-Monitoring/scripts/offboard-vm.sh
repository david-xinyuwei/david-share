#!/usr/bin/env bash
# Remove GPU-hours collection from one VM: gpumon collector, rule and endpoint associations, Azure Monitor Agent.
# The NVIDIA driver, the DCGM package and the managed identity stay.
#
# Usage: ./offboard-vm.sh -g <vm-resource-group> -n <vm-name>
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: keep /subscriptions/... arguments unchanged

RG=""; VM=""
while getopts "g:n:h" opt; do
  case $opt in g) RG=$OPTARG ;; n) VM=$OPTARG ;; *) sed -n '2,5p' "$0"; exit 1 ;; esac
done
[[ -n "$RG" && -n "$VM" ]] || { sed -n '2,5p' "$0"; exit 1; }

az extension add --upgrade --yes --name monitor-control-service -o none
VM_ID=$(az vm show -g "$RG" -n "$VM" --query id -o tsv)

echo "==> stop and remove the gpumon collector"
az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --query "value[0].message" -o tsv --scripts \
  "systemctl disable --now gpumon 2>/dev/null; rm -rf /opt/gpumon /var/log/gpumon /etc/systemd/system/gpumon.service; systemctl daemon-reload; echo gpumon removed"

echo "==> remove the rule and endpoint associations"
az monitor data-collection rule association delete --name dcra-gpu-hours --resource "$VM_ID" --yes -o none || true
az monitor data-collection rule association delete --name configurationAccessEndpoint --resource "$VM_ID" --yes -o none || true

echo "==> remove the Azure Monitor Agent"
az vm extension delete -g "$RG" --vm-name "$VM" -n AzureMonitorLinuxAgent -o none

echo "==> $VM offboarded"
