#!/usr/bin/env bash
# Deploy the lre-steering-agent Hosted Agent into an existing Foundry project.
# All identifiers come from the environment; nothing customer-specific is stored here.
set -euo pipefail

: "${AZD_BIN:=azd}"
: "${AZURE_SUBSCRIPTION_ID:?set AZURE_SUBSCRIPTION_ID}"
: "${AZURE_LOCATION:?set AZURE_LOCATION to a region that offers Hosted Agents}"
: "${AZURE_AI_PROJECT_ID:?set AZURE_AI_PROJECT_ID to the Foundry project ARM resource ID}"
: "${AZURE_AI_PROJECT_ENDPOINT:?set AZURE_AI_PROJECT_ENDPOINT to the Foundry project endpoint}"
: "${LRA_TRANSLATOR_RESOURCE_ID:?set LRA_TRANSLATOR_RESOURCE_ID to the Translator ARM resource ID}"
: "${LRA_TRANSLATOR_ENDPOINT:=https://api.cognitive.microsofttranslator.com}"
: "${LRA_TRANSLATOR_REGION:=global}"
: "${AZD_ENV_NAME:=lre-steering-agent-dev}"

cd "$(dirname "$0")/.."

if ! "$AZD_BIN" env list 2>/dev/null | grep -q "${AZD_ENV_NAME}"; then
  "$AZD_BIN" env new "${AZD_ENV_NAME}" \
    --subscription "${AZURE_SUBSCRIPTION_ID}" \
    --location "${AZURE_LOCATION}" \
    --no-prompt
fi
"$AZD_BIN" env select "${AZD_ENV_NAME}"

"$AZD_BIN" env set USE_EXISTING_AI_PROJECT true
"$AZD_BIN" env set AZD_AGENT_SKIP_ACR true
"$AZD_BIN" env set ENABLE_HOSTED_AGENTS true
"$AZD_BIN" env set ENABLE_CAPABILITY_HOST false
"$AZD_BIN" env set AZURE_AI_PROJECT_ID "${AZURE_AI_PROJECT_ID}"
"$AZD_BIN" env set AZURE_AI_PROJECT_ENDPOINT "${AZURE_AI_PROJECT_ENDPOINT}"
"$AZD_BIN" env set FOUNDRY_PROJECT_ENDPOINT "${AZURE_AI_PROJECT_ENDPOINT}"
"$AZD_BIN" env set LRA_TRANSLATOR_ENDPOINT "${LRA_TRANSLATOR_ENDPOINT}"
"$AZD_BIN" env set LRA_TRANSLATOR_REGION "${LRA_TRANSLATOR_REGION}"
"$AZD_BIN" env set LRA_TRANSLATOR_RESOURCE_ID "${LRA_TRANSLATOR_RESOURCE_ID}"
"$AZD_BIN" env set LRE_STAGE_DELAY_MS "${LRE_STAGE_DELAY_MS:-300}"
# Fault injection is a test-only affordance; leave it false for a customer-facing deployment.
"$AZD_BIN" env set LRE_ENABLE_FAULT_INJECTION "${LRE_ENABLE_FAULT_INJECTION:-false}"

"$AZD_BIN" deploy lre-steering-agent --no-prompt
