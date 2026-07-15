#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENVIRONMENT_NAME="${AZURE_ENV_NAME:-meeting-agent-dev}"
LOCATION="${AZURE_LOCATION:-eastus2}"
MODEL_DEPLOYMENT_NAME="${AZURE_AI_MODEL_DEPLOYMENT_NAME:-gpt-5.4-mini}"

subscription_id="$(az account show --only-show-errors --query id --output tsv)"
tenant_id="$(az account show --only-show-errors --query tenantId --output tsv)"
subscription_name="$(az account show --only-show-errors --query name --output tsv)"
subscription_state="$(az account show --only-show-errors --query state --output tsv)"

if [[ -z "$subscription_id" || -z "$tenant_id" ]]; then
	echo "Azure CLI did not return a tenant and subscription. Sign in with az first." >&2
	exit 1
fi
if [[ "$subscription_state" != "Enabled" ]]; then
	echo "Azure subscription '$subscription_name' is not enabled." >&2
	exit 1
fi

azd config set auth.useAzCliAuth true
if ! azd env select "$ENVIRONMENT_NAME" --no-prompt >/dev/null 2>&1; then
	azd env new "$ENVIRONMENT_NAME" \
		--subscription "$subscription_id" \
		--location "$LOCATION" \
		--no-prompt
fi
azd env set AZURE_SUBSCRIPTION_ID "$subscription_id"
azd env set AZURE_TENANT_ID "$tenant_id"
azd env set AZURE_LOCATION "$LOCATION"
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "$MODEL_DEPLOYMENT_NAME"

printf 'Deploying Meeting Agent to %s (%s), tenant %s, region %s.\n' \
	"$subscription_name" "$subscription_id" "$tenant_id" "$LOCATION"
azd up --no-prompt
exec "$ROOT_DIR/scripts/start-ui.sh"