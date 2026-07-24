#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
: "${AZURE_CONFIG_DIR:?Set the isolated AZURE_CONFIG_DIR first}"
: "${AZD_CONFIG_DIR:?Set the isolated AZD_CONFIG_DIR first}"
: "${AZURE_TENANT_ID:?Set the target AZURE_TENANT_ID first}"
: "${AZURE_SUBSCRIPTION_ID:?Set the target AZURE_SUBSCRIPTION_ID first}"

command -v az >/dev/null
command -v azd >/dev/null

account=$(az account show --output json)
ACCOUNT_JSON="$account" python3 - <<'PY'
import json
import os

account = json.loads(os.environ["ACCOUNT_JSON"])
assert account["tenantId"] == os.environ["AZURE_TENANT_ID"]
assert account["id"] == os.environ["AZURE_SUBSCRIPTION_ID"]
assert account["state"] == "Enabled"
PY
az provider show --namespace Microsoft.CognitiveServices \
  --query registrationState --output tsv | grep -Fx Registered >/dev/null
azd auth status >/dev/null

environment_name=$(python3 - <<PY
import json
from pathlib import Path
print(json.loads(Path("$ROOT/.azure/config.json").read_text())["defaultEnvironment"])
PY
)
deploy_root="$ROOT/.azure/deploy-source"
environment_json="$ROOT/.azure/deploy-environment.json"
azd env get-values --environment "$environment_name" --no-prompt -o json \
  >"$environment_json"
python3 "$ROOT/scripts/render_deployment_source.py" \
  --env-json "$environment_json" \
  --output-dir "$deploy_root"

public_azure_yaml="$ROOT/azure.yaml"
backup_azure_yaml="$ROOT/.azure/public-azure.yaml.backup"
cp "$public_azure_yaml" "$backup_azure_yaml"
restore_public_yaml() {
  cp "$backup_azure_yaml" "$public_azure_yaml"
  rm -f "$backup_azure_yaml"
}
trap restore_public_yaml EXIT
cp "$deploy_root/azure.yaml" "$public_azure_yaml"

azd deploy managed-meeting-agent \
  --cwd "$ROOT" \
  --environment "$environment_name" \
  --no-prompt