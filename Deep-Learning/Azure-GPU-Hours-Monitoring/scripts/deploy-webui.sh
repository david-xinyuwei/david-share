#!/usr/bin/env bash
# Deploy the standalone dashboard / JSON API to Azure App Service (Linux, Python).
#
#   App Service plan (B1) + Web App, system-assigned managed identity
#   "Log Analytics Reader" on the workspace only (least privilege)
#   HTTPS-only, TLS 1.2+, FTPS off, access code via ACCESS_CODE app setting
#
# Usage:
#   ./deploy-webui.sh -g <resource-group> -n <globally-unique-webapp-name> -w <workspace-guid> -l <location> \
#                     [-a <law-name>] [-c <access-code>] [-s <sku>]
#
# The access code is printed once at the end; rotate it any time in App Service > Configuration > ACCESS_CODE.
set -euo pipefail

RG=""; APP=""; WS_GUID=""; LOC=""; LAW="law-gpuhours"; CODE=""; SKU="B1"
while getopts "g:n:w:l:a:c:s:h" opt; do
  case $opt in
    g) RG=$OPTARG ;; n) APP=$OPTARG ;; w) WS_GUID=$OPTARG ;; l) LOC=$OPTARG ;;
    a) LAW=$OPTARG ;; c) CODE=$OPTARG ;; s) SKU=$OPTARG ;;
    h|*) sed -n '2,13p' "$0"; exit 0 ;;
  esac
done
[[ -z "$RG" || -z "$APP" || -z "$WS_GUID" || -z "$LOC" ]] && { echo "usage: $0 -g <rg> -n <app> -w <workspace-guid> -l <location> [-a law] [-c code] [-s sku]"; exit 1; }
[[ -z "$CODE" ]] && CODE=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16)

HERE=$(cd "$(dirname "$0")" && pwd)
WEB_DIR="$HERE/../webui"
PLAN="asp-$APP"
SUB=$(az account show --query id -o tsv)
LAW_ID="/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.OperationalInsights/workspaces/$LAW"

echo "==> App Service plan + web app ($SKU Linux, Python 3.12)"
az appservice plan create -g "$RG" -n "$PLAN" -l "$LOC" --is-linux --sku "$SKU" -o none
az webapp create -g "$RG" -p "$PLAN" -n "$APP" --runtime "PYTHON:3.12" -o none

echo "==> managed identity -> Log Analytics Reader on $LAW"
PRINCIPAL=$(az webapp identity assign -g "$RG" -n "$APP" --query principalId -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Log Analytics Reader" --scope "$LAW_ID" -o none

echo "==> settings + hardening"
az webapp config appsettings set -g "$RG" -n "$APP" --settings \
  WORKSPACE_ID="$WS_GUID" ACCESS_CODE="$CODE" CACHE_SECONDS=60 TZ_HOURS=8 SCM_DO_BUILD_DURING_DEPLOYMENT=true -o none
az webapp config set -g "$RG" -n "$APP" \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 180 --workers 2 --threads 8 app:app" \
  --always-on true --min-tls-version 1.2 --ftps-state Disabled -o none
az webapp update -g "$RG" -n "$APP" --https-only true -o none

echo "==> zip deploy"
STAGE=$(mktemp -d); ZIP=$(mktemp --suffix=.zip)
cp "$WEB_DIR/app.py" "$WEB_DIR/requirements.txt" "$STAGE/"; cp -r "$WEB_DIR/static" "$STAGE/"
(cd "$STAGE" && zip -qr "$ZIP" .)
az webapp deploy -g "$RG" -n "$APP" --src-path "$ZIP" --type zip -o none
rm -rf "$STAGE" "$ZIP"

HOST=$(az webapp show -g "$RG" -n "$APP" --query defaultHostName -o tsv)
cat <<EOF

==> Dashboard:  https://$HOST
    Login:      any username, password = $CODE
    API:        https://$HOST/api/data?range=24h&idle=5   (same Basic auth)
    Health:     https://$HOST/healthz

First request after deploy takes ~1-2 min while pip installs; subsequent requests are cached 60 s.
EOF
