#!/usr/bin/env bash
# Read GPU hours the way your platform does: sign in to Entra ID with the client-credentials flow, then send one
# POST to the Log Analytics query API with the bearer token. Needs only curl and jq; no Azure CLI.
#
# Usage: ./query-gpu-hours.sh -c <gpu-hours.query.env> -q <kql-file> [-t <timespan>]
#   timespan: ISO 8601 duration such as PT1H or P1D, or <start>/<end>; default P1D
# Exit codes: 0 rows printed as JSON objects; 4 sign-in rejected (tenant, client ID or secret);
#             5 query rejected (no Log Analytics Reader yet, wrong workspace, or a query error); 1 other errors.
set -euo pipefail
die() { echo "ERROR: $1" >&2; exit "${2:-1}"; }
usage() { sed -n '2,8p' "$0"; exit 1; }

CFG=""; KQL=""; SPAN="P1D"
while getopts "c:q:t:h" opt; do
  case $opt in
    c) CFG=$OPTARG ;; q) KQL=$OPTARG ;; t) SPAN=$OPTARG ;;
    *) usage ;;
  esac
done
[[ -n "$CFG" && -n "$KQL" ]] || usage
[[ -f "$CFG" ]] || die "settings file $CFG not found"
[[ -f "$KQL" ]] || die "query file $KQL not found"
CURL=${GPUHOURS_CURL:-curl}  # tests point this at a stub
command -v "$CURL" >/dev/null || die "curl is required"
command -v jq >/dev/null || die "jq is required"

AZURE_TENANT_ID=""; AZURE_CLIENT_ID=""; AZURE_CLIENT_SECRET=""; WORKSPACE_GUID=""
while IFS='=' read -r key value; do
  value=${value%$'\r'}
  case $key in
    AZURE_TENANT_ID) AZURE_TENANT_ID=$value ;; AZURE_CLIENT_ID) AZURE_CLIENT_ID=$value ;;
    AZURE_CLIENT_SECRET) AZURE_CLIENT_SECRET=$value ;; WORKSPACE_GUID) WORKSPACE_GUID=$value ;;
  esac
done < "$CFG"
for name in AZURE_TENANT_ID AZURE_CLIENT_ID AZURE_CLIENT_SECRET WORKSPACE_GUID; do
  [[ -n "${!name}" ]] || die "$name is missing in $CFG"
done

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
chmod 700 "$TMP"

# 1. Sign in. The secret goes to curl on stdin, so it never appears in a command line or process list.
CODE=$(printf '%s' "$AZURE_CLIENT_SECRET" | "$CURL" -sS -o "$TMP/token.json" -w '%{http_code}' -X POST \
  "https://login.microsoftonline.com/$AZURE_TENANT_ID/oauth2/v2.0/token" \
  --data-urlencode grant_type=client_credentials \
  --data-urlencode "client_id=$AZURE_CLIENT_ID" \
  --data-urlencode "client_secret@-" \
  --data-urlencode "scope=https://api.loganalytics.io/.default") || die "cannot reach login.microsoftonline.com"
if [[ "$CODE" != 200 ]]; then
  REASON=$(jq -r '(.error // "unknown") + ": " + ((.error_description // "") | split("\r\n")[0] | split("\n")[0])' \
    "$TMP/token.json" 2>/dev/null | tr -d '\r') || REASON="unreadable response"
  die "sign-in rejected (HTTP $CODE) $REASON" 4
fi
TOKEN=$(jq -r '.access_token // empty' "$TMP/token.json" | tr -d '\r')
[[ -n "$TOKEN" ]] || die "sign-in returned no access token" 4
echo "signed in as client $AZURE_CLIENT_ID (token for https://api.loganalytics.io)" >&2

# 2. Query. The token goes to curl in a header file, again never on a command line.
printf 'Authorization: Bearer %s\n' "$TOKEN" > "$TMP/auth.header"
unset TOKEN AZURE_CLIENT_SECRET
jq -n --rawfile q "$KQL" --arg t "$SPAN" '{query: $q, timespan: $t}' > "$TMP/body.json"
CODE=$("$CURL" -sS -o "$TMP/result.json" -w '%{http_code}' -X POST \
  "https://api.loganalytics.azure.com/v1/workspaces/$WORKSPACE_GUID/query" \
  -H @"$TMP/auth.header" -H "Content-Type: application/json" --data-binary @"$TMP/body.json") \
  || die "cannot reach api.loganalytics.azure.com"
if [[ "$CODE" != 200 ]] || jq -e '.error' "$TMP/result.json" >/dev/null 2>&1; then
  REASON=$(jq -r '(.error.code // "unknown") + ": " + (.error.message // "")' "$TMP/result.json" 2>/dev/null \
    | tr -d '\r') || REASON="unreadable response"
  die "query rejected (HTTP $CODE) $REASON" 5
fi
echo "query $(basename "$KQL") over $SPAN: HTTP 200" >&2
jq '.tables[0] as $t | [$t.rows[] as $r | [$t.columns | to_entries[] | {key: .value.name, value: $r[.key]}] | from_entries]' \
  "$TMP/result.json"
