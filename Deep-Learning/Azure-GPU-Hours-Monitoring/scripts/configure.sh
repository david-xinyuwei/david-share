#!/usr/bin/env bash
# One command for the whole setup: preflight, workspace and rule, AML job tracking, every GPU VM, query access
# for your platform and a check that GPU rows arrive. Copy scripts/gpu-hours.env.example, fill it in, then run:
#
# Usage: ./configure.sh -c <settings-file> [-p | -v]
#   -p  preflight only: read-only checks of the login, the VMs and DCGM; changes nothing
#   -v  verify only: wait until every VM's GPU rows arrive in the workspace
# Re-running is safe: every step creates or updates in place. Exit codes: 1 settings or preflight,
# 2 a VM failed to onboard, 3 GPU rows did not arrive within WAIT_MINUTES.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: keep /subscriptions/... arguments unchanged

usage() { sed -n '2,9p' "$0"; exit 1; }
CONFIG=""; MODE=all
while getopts "c:pvh" opt; do
  case $opt in c) CONFIG=$OPTARG ;; p) MODE=preflight ;; v) MODE=verify ;; *) usage ;; esac
done
[[ -n "$CONFIG" && -f "$CONFIG" ]] || usage
HERE=$(cd "$(dirname "$0")" && pwd)

SUBSCRIPTION_ID=""; WORKSPACE_RG=""; LOCATION=""; WORKSPACE_NAME="law-gpu-hours"; RETENTION_DAYS=90
VM_RG=""; VMSS_NAME=""; VM_NAMES=""; AML_WORKSPACE_ID=""; READER_OBJECT_ID=""; READER_PRINCIPAL_TYPE=ServicePrincipal
SKIP_NOT_READY_VMS=0; PARALLEL=5; WAIT_MINUTES=20; FAILED=0
SETTINGS="settings.$$.env"  # the settings file may have been saved with Windows line endings
tr -d '\r' < "$CONFIG" > "$SETTINGS"
# shellcheck disable=SC1090
source "$SETTINGS"
rm -f "$SETTINGS"

die() { echo "ERROR: $*" >&2; exit "${2:-1}"; }
step() { printf '\n==> [%s] %s\n' "$1" "$2"; }
clean() { tr -d '\r'; }
[[ -n "$WORKSPACE_RG" && -n "$LOCATION" && -n "$VM_RG" ]] || die "set WORKSPACE_RG, LOCATION and VM_RG in $CONFIG"
[[ -n "$VMSS_NAME$VM_NAMES" ]] || die "set VMSS_NAME, VM_NAMES or both in $CONFIG"
[[ "$PARALLEL" =~ ^[1-9][0-9]*$ && "$WAIT_MINUTES" =~ ^[0-9]+$ ]] || die "PARALLEL and WAIT_MINUTES must be whole numbers"

LOG_DIR="gpu-hours-logs/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$LOG_DIR"
PROBE="preflight.$$.sh"; BODY="query.$$.json"  # relative paths: readable by the Windows and the Linux Azure CLI alike
trap 'rm -f "$PROBE" "$BODY"' EXIT
echo "logs: $LOG_DIR"

# run_parallel <function> <vm>...: at most PARALLEL VMs at a time; each call records its own result file
run_parallel() {
  local fn=$1 pids=() vm; shift
  for vm in "$@"; do
    "$fn" "$vm" & pids+=($!)
    if (( ${#pids[@]} >= PARALLEL )); then wait "${pids[@]}" || true; pids=(); fi
  done
  if (( ${#pids[@]} > 0 )); then wait "${pids[@]}" || true; fi
}

step 1 "Azure login and subscription"
[[ -z "$SUBSCRIPTION_ID" ]] || az account set --subscription "$SUBSCRIPTION_ID"
az account show --query "{subscription: name, signedInAs: user.name}" -o table || die "run az login first"

step 2 "GPU VMs"
VMS=()
add_vm() {
  local v=$1 x
  [[ -n "$v" ]] || return 0
  for x in "${VMS[@]+"${VMS[@]}"}"; do [[ "$x" == "$v" ]] && return 0; done
  VMS+=("$v")
}
if [[ -n "$VMSS_NAME" ]]; then
  ORCH=$(az vmss show -g "$VM_RG" -n "$VMSS_NAME" --query orchestrationMode -o tsv | clean)
  [[ "$ORCH" == Flexible ]] || die "scale set $VMSS_NAME uses $ORCH orchestration; only Flexible scale set instances are standalone VMs that this script can onboard"
  while read -r v; do add_vm "$v"; done < <(az vmss list-instances -g "$VM_RG" -n "$VMSS_NAME" --query "[].name" -o tsv | clean)
fi
for v in $VM_NAMES; do add_vm "$v"; done
(( ${#VMS[@]} > 0 )) || die "no VM found in $VM_RG"
echo "${#VMS[@]} VM(s): ${VMS[*]}"

if [[ "$MODE" != verify ]]; then
  step 3 "preflight: running, NVIDIA driver, DCGM, python3 (Run Command, read-only)"
  cat > "$PROBE" <<'EOF'
#!/bin/bash
ok=1
if command -v nvidia-smi >/dev/null; then echo "gpus: $(nvidia-smi -L | wc -l)"; else echo "missing: nvidia-smi (NVIDIA driver)"; ok=0; fi
if command -v dcgmi >/dev/null; then echo "dcgm: $(dcgmi --version | grep -io 'version *: *[0-9.]*' | grep -o '[0-9.]*$' | head -1)"
else echo "missing: dcgmi (datacenter-gpu-manager package)"; ok=0; fi
[ -x /usr/bin/python3 ] || { echo "missing: /usr/bin/python3"; ok=0; }
command -v systemctl >/dev/null || { echo "missing: systemd"; ok=0; }
if [ "$ok" = 1 ]; then echo PREFLIGHT_OK; else echo PREFLIGHT_FAIL; fi
EOF
  check_vm() {
    local vm=$1 log="$LOG_DIR/preflight.$1.log" power out
    power=$(az vm show -d -g "$VM_RG" -n "$vm" --query powerState -o tsv 2>>"$log" | clean) || true
    if [[ "$power" != "VM running" ]]; then echo "NOT_READY ${power:-VM not found}" > "$log.status"; return 0; fi
    out=$(az vm run-command invoke -g "$VM_RG" -n "$vm" --command-id RunShellScript --scripts "@$PROBE" \
      --query "value[0].message" -o tsv 2>>"$log" | clean) || true
    printf '%s\n' "$out" >> "$log"
    if grep -q PREFLIGHT_OK <<<"$out"; then
      echo "OK $(grep -E '^(gpus|dcgm):' <<<"$out" | paste -sd' ' -)" > "$log.status"
    else
      echo "NOT_READY $(grep '^missing:' <<<"$out" | paste -sd';' - || true) (details: $log)" > "$log.status"
    fi
  }
  run_parallel check_vm "${VMS[@]}"
  READY=()
  for vm in "${VMS[@]}"; do
    status=$(cat "$LOG_DIR/preflight.$vm.log.status" 2>/dev/null || echo "NOT_READY no result")
    printf '  %-40s %s\n' "$vm" "$status"
    [[ "$status" == OK* ]] && READY+=("$vm")
  done
  if (( ${#READY[@]} < ${#VMS[@]} )); then
    [[ "$SKIP_NOT_READY_VMS" == 1 ]] || die "$(( ${#VMS[@]} - ${#READY[@]} )) VM(s) not ready; fix them, or set SKIP_NOT_READY_VMS=1 to onboard only the ready ones"
    (( ${#READY[@]} > 0 )) || die "no VM is ready"
    echo "continuing with ${#READY[@]} ready VM(s)"
  fi
  if [[ "$MODE" == preflight ]]; then echo; echo "preflight passed; nothing was changed"; exit 0; fi
  VMS=("${READY[@]}")

  step 4 "workspace, GpuMetrics_CL table, data collection endpoint and rule$([[ -n "$AML_WORKSPACE_ID" ]] && echo ', AML job tracking')"
  SETUP_ARGS=(-g "$WORKSPACE_RG" -l "$LOCATION" -w "$WORKSPACE_NAME" -r "$RETENTION_DAYS")
  [[ -z "$AML_WORKSPACE_ID" ]] || SETUP_ARGS+=(-a "$AML_WORKSPACE_ID")
  bash "$HERE/setup-workspace.sh" "${SETUP_ARGS[@]}" 2>&1 | tee "$LOG_DIR/setup-workspace.log"
  value() { sed -n "s/^$1=//p" "$LOG_DIR/setup-workspace.log" | clean | tail -1; }
  DCR_ID=$(value DCR_ID); DCE_ID=$(value DCE_ID)
  [[ -n "$DCR_ID" && -n "$DCE_ID" ]] || die "setup-workspace.sh did not print DCR_ID and DCE_ID; see $LOG_DIR/setup-workspace.log"

  step 5 "onboard ${#VMS[@]} VM(s), $PARALLEL at a time: Azure Monitor Agent, rule association, DCGM, gpumon"
  onboard() {
    local vm=$1 log="$LOG_DIR/onboard.$1.log"
    if GPUHOURS_SKIP_CLI_EXTENSION=1 bash "$HERE/onboard-vm.sh" -g "$VM_RG" -n "$vm" -d "$DCR_ID" -e "$DCE_ID" >"$log" 2>&1 \
       && grep -q "active (running)" "$log"; then
      echo OK > "$log.status"
    else
      echo "FAILED (details: $log)" > "$log.status"
    fi
  }
  run_parallel onboard "${VMS[@]}"
  ONBOARDED=()
  for vm in "${VMS[@]}"; do
    status=$(cat "$LOG_DIR/onboard.$vm.log.status" 2>/dev/null || echo "FAILED no result")
    printf '  %-40s %s\n' "$vm" "$status"
    if [[ "$status" == OK ]]; then ONBOARDED+=("$vm"); else FAILED=$((FAILED + 1)); fi
  done
  (( ${#ONBOARDED[@]} > 0 )) || die "no VM was onboarded" 2
  VMS=("${ONBOARDED[@]}")
fi

LAW_ID=$(az monitor log-analytics workspace show -g "$WORKSPACE_RG" -n "$WORKSPACE_NAME" --query id -o tsv | clean)
WORKSPACE_GUID=$(az monitor log-analytics workspace show -g "$WORKSPACE_RG" -n "$WORKSPACE_NAME" --query customerId -o tsv | clean)
[[ -n "$LAW_ID" && -n "$WORKSPACE_GUID" ]] || die "workspace $WORKSPACE_NAME not found in $WORKSPACE_RG"

if [[ "$MODE" == all ]]; then
  step 6 "query access for your platform"
  if [[ -n "$READER_OBJECT_ID" ]]; then
    az role assignment create --assignee-object-id "$READER_OBJECT_ID" --assignee-principal-type "$READER_PRINCIPAL_TYPE" \
      --role "Log Analytics Reader" --scope "$LAW_ID" -o none
    echo "Log Analytics Reader granted to $READER_OBJECT_ID"
  else
    echo "READER_OBJECT_ID is empty; grant it later with the command in the quick start"
  fi
  {
    echo "WORKSPACE_GUID=$WORKSPACE_GUID"
    echo "WORKSPACE_RESOURCE_ID=$LAW_ID"
    echo "DCR_ID=$DCR_ID"
    echo "DCE_ID=$DCE_ID"
    echo "ONBOARDED_VMS=\"${VMS[*]}\""
    echo "JOB_TRACKING=$([[ -n "$AML_WORKSPACE_ID" ]] && echo enabled || echo disabled)"
  } > gpu-hours.outputs.env
  echo "values for your platform saved to gpu-hours.outputs.env"
fi

step 7 "wait for GPU rows from every VM (up to $WAIT_MINUTES minutes; the first rows take about 10 minutes)"
# The same Log Analytics query API your platform calls, through az rest.
printf '{"query": "GpuMetrics_CL | where TimeGenerated > ago(30m) | summarize Rows = count(), Last = max(TimeGenerated) by VmName", "timespan": "PT1H"}\n' > "$BODY"
DEADLINE=$(( $(date +%s) + WAIT_MINUTES * 60 ))
while :; do
  ROWS=$(az rest --method post --url "https://api.loganalytics.io/v1/workspaces/$WORKSPACE_GUID/query" \
    --resource https://api.loganalytics.io --body "@$BODY" --query "tables[0].rows" -o tsv 2>>"$LOG_DIR/verify.log" | clean) || ROWS=""
  MISSING=()
  for vm in "${VMS[@]}"; do
    awk -F'\t' -v v="$vm" 'tolower($1) == tolower(v) { found = 1 } END { exit !found }' <<<"$ROWS" || MISSING+=("$vm")
  done
  if (( ${#MISSING[@]} == 0 )); then
    printf 'VmName\tRows (30 min)\tLast\n%s\n' "$ROWS" | sed 's/^/  /'
    echo "all ${#VMS[@]} VM(s) are sending GPU rows"
    break
  fi
  if (( $(date +%s) >= DEADLINE )); then
    die "no GPU rows yet from: ${MISSING[*]}. New VMs can take 15 minutes; re-run with -v. Details: $LOG_DIR" 3
  fi
  echo "  $(( ${#VMS[@]} - ${#MISSING[@]} ))/${#VMS[@]} VM(s) reporting; checking again in 60 s"
  sleep 60
done

cat <<EOF

==> done
WORKSPACE_GUID=$WORKSPACE_GUID
Query from your platform: POST https://api.loganalytics.io/v1/workspaces/$WORKSPACE_GUID/query
  body {"query": "<content of a kql/*.kql file>", "timespan": "<start>/<end>"}, token for https://api.loganalytics.io,
  identity with Log Analytics Reader on the workspace. Python: examples/gpu_hours_client.py.
EOF
if [[ -n "$AML_WORKSPACE_ID" ]]; then
  echo "AML jobs: every GPU process must carry AZUREML_RUN_ID (ssh: env AZUREML_RUN_ID=..., mpirun: -x AZUREML_RUN_ID)."
fi
if [[ "$MODE" == all ]] && (( FAILED > 0 )); then die "$FAILED VM(s) failed to onboard; fix them and re-run" 2; fi
