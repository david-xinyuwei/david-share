#!/usr/bin/env bash
# Remove only the Azure resources created by setup-workspace.sh. Offboard every VM first.
#
# Usage: ./remove-workspace.sh -g <resource-group> [-w <workspace-name>] [-a <aml-workspace-resource-id>] -y
# Without -y, prints the deletion plan and changes nothing. The resource group itself is never deleted.
set -euo pipefail
export MSYS_NO_PATHCONV=1
az() {
  if [[ -n "${GPUHOURS_SUBSCRIPTION_ID:-}" && "$1" != extension ]]; then
    command az "$@" --subscription "$GPUHOURS_SUBSCRIPTION_ID"
  else
    command az "$@"
  fi
}
hash8() {
  if command -v sha256sum >/dev/null; then sha256sum | cut -c1-8
  else shasum -a 256 | cut -c1-8; fi
}

RG=""; LAW="law-gpu-hours"; AML_ID=""; CONFIRM=0
while getopts "g:w:a:yh" opt; do
  case $opt in
    g) RG=$OPTARG ;; w) LAW=$OPTARG ;; a) AML_ID=$OPTARG ;; y) CONFIRM=1 ;;
    *) sed -n '2,5p' "$0"; exit 1 ;;
  esac
done
[[ -n "$RG" ]] || { sed -n '2,5p' "$0"; exit 1; }
LAW_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query id -o tsv)
LAW_HASH=$(printf '%s' "$LAW_ID" | hash8)
DCR="dcr-gpu-hours-$LAW_HASH"; DCE="dce-gpu-hours-$LAW_HASH"
SUB_DIAG="gpu-hours-job-submitters-$LAW_HASH"; AML_DIAG="gpu-hours-job-status-$LAW_HASH"

cat <<EOF
Resources to remove:
  workspace: $RG/$LAW
  data collection rule: $RG/$DCR
  data collection endpoint: $RG/$DCE
  AML diagnostics: $([[ -n "$AML_ID" ]] && echo "$AML_ID" || echo "not requested")
The resource group is not deleted. Offboard every VM before continuing.
EOF
if [[ "$CONFIRM" != 1 ]]; then
  echo "Dry run only. Add -y to remove these resources."
  exit 0
fi

az extension add --upgrade --yes --name monitor-control-service -o none
if [[ -n "$AML_ID" ]]; then
  az monitor diagnostic-settings subscription delete -n "$SUB_DIAG" --yes -o none
  az monitor diagnostic-settings delete -n "$AML_DIAG" --resource "$AML_ID" -o none
fi
az monitor data-collection rule delete -g "$RG" -n "$DCR" --yes -o none
az monitor data-collection endpoint delete -g "$RG" -n "$DCE" --yes -o none
az monitor log-analytics workspace delete -g "$RG" -n "$LAW" --yes -o none
echo "GPU-hours workspace resources removed; resource group $RG kept"
