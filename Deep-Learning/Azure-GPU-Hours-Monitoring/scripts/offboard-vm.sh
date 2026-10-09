#!/usr/bin/env bash
# Remove GPU-hours collection from one VM: gpumon collector and this deployment's rule and endpoint associations.
# The shared Azure Monitor Agent, NVIDIA driver, DCGM package and managed identity stay.
#
# Usage: ./offboard-vm.sh -g <vm-resource-group> -n <vm-name> -d <dcr-resource-id> -e <dce-resource-id>
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
    *) sed -n '2,5p' "$0"; exit 1 ;;
  esac
done
[[ -n "$RG" && -n "$VM" && -n "$DCR_ID" && -n "$DCE_ID" ]] || { sed -n '2,5p' "$0"; exit 1; }

az extension add --upgrade --yes --name monitor-control-service -o none
VM_ID=$(az vm show -g "$RG" -n "$VM" --query id -o tsv)
DCR_NAME=${DCR_ID##*/}
DCR_ASSOC="dcra-$DCR_NAME"

echo "==> stop and remove the gpumon collector"
RUN_OUTPUT=$(az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --query "value[0].message" -o tsv --scripts \
  "set -eu; systemctl disable --now gpumon 2>/dev/null || [ ! -e /etc/systemd/system/gpumon.service ]; rm -rf /opt/gpumon /var/log/gpumon /etc/systemd/system/gpumon.service; systemctl daemon-reload; [ ! -e /etc/systemd/system/gpumon.service ]; echo gpumon removed")
printf '%s\n' "$RUN_OUTPUT"
grep -q "gpumon removed" <<<"$RUN_OUTPUT" || { echo "ERROR: guest did not confirm gpumon removal" >&2; exit 1; }

echo "==> remove the rule and endpoint associations"
ASSOCIATION_NAMES=$(az monitor data-collection rule association list --resource "$VM_ID" --query "[].name" -o tsv)
if grep -Fxq "$DCR_ASSOC" <<<"$ASSOCIATION_NAMES"; then
  az monitor data-collection rule association delete --name "$DCR_ASSOC" --resource "$VM_ID" --yes -o none
fi
EXISTING_DCE=$(az monitor data-collection rule association list --resource "$VM_ID" \
  --query "[?name=='configurationAccessEndpoint'].dataCollectionEndpointId | [0]" -o tsv)
if [[ -n "$EXISTING_DCE" && "${EXISTING_DCE,,}" == "${DCE_ID,,}" ]]; then
  OTHER_DCRS=$(az monitor data-collection rule association list --resource "$VM_ID" \
    --query "[?dataCollectionRuleId != null && name != '$DCR_ASSOC'].name" -o tsv)
  if [[ -z "$OTHER_DCRS" ]]; then
    az monitor data-collection rule association delete --name configurationAccessEndpoint --resource "$VM_ID" --yes -o none
  else
    echo "==> other DCR associations still use the DCE; leaving configurationAccessEndpoint: $OTHER_DCRS"
  fi
elif [[ -n "$EXISTING_DCE" ]]; then
  echo "==> another DCE owns configurationAccessEndpoint; leaving it: $EXISTING_DCE"
fi

echo "==> $VM offboarded"
