#!/usr/bin/env bash
# Run a KQL query against the workspace through the Log Analytics Query REST API.
# This is the exact call a customer platform makes to integrate GPU-hours data.
#
# Usage:
#   ./query.sh -w <workspace-guid> -q 'GpuMetrics_CL | take 5' [-t P1D]
#   ./query.sh -w <workspace-guid> -f ../azure/queries.kql            # first query block in the file
#
# Auth: az CLI token for https://api.loganalytics.io. In production use a managed identity
# or service principal with "Log Analytics Reader" on the workspace.
set -euo pipefail

WS=""; KQL=""; FILE=""; SPAN="P7D"
while getopts "w:q:f:t:h" opt; do
  case $opt in
    w) WS=$OPTARG ;; q) KQL=$OPTARG ;; f) FILE=$OPTARG ;; t) SPAN=$OPTARG ;;
    h|*) sed -n '2,11p' "$0"; exit 0 ;;
  esac
done
[[ -z "$WS" ]] && { echo "usage: $0 -w <workspace-guid> (-q <kql> | -f <file>) [-t <ISO8601 timespan>]"; exit 1; }
if [[ -n "$FILE" ]]; then
  # take the first block (up to the first blank line), strip // comments, replace workbook params
  KQL=$(awk 'NF==0{exit} !/^\/\//{print}' "$FILE" \
        | sed -e 's/{TimeRange:seconds}/86400/g' -e 's/{TimeRange}/> ago(1d)/g' -e "s/{Computer}/'*'/g" -e 's/{IdlePct}/5/g')
fi
[[ -z "$KQL" ]] && { echo "no query given"; exit 1; }

# JSON-encode the query safely (python3 preferred; fall back to python for Windows Git-bash where python3 may be a store stub)
PY=$(command -v python3 || command -v python) || { echo "python not found"; exit 1; }
BODY=$("$PY" -c 'import json,sys; print(json.dumps({"query": sys.argv[1], "timespan": sys.argv[2]}))' "$KQL" "$SPAN" 2>/dev/null) \
  || BODY=$(python -c 'import json,sys; print(json.dumps({"query": sys.argv[1], "timespan": sys.argv[2]}))' "$KQL" "$SPAN")
az rest --method post --url "https://api.loganalytics.io/v1/workspaces/$WS/query" \
  --resource "https://api.loganalytics.io" --headers "Content-Type=application/json" --body "$BODY" \
  --query "tables[0].{columns:columns[].name, rows:rows}" -o json
