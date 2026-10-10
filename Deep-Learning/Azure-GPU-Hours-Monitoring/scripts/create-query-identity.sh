#!/usr/bin/env bash
# Create or reuse the identity your platform signs in with to read GPU hours: an Entra ID app registration,
# its service principal, a client secret, and Log Analytics Reader on the workspace (read-only, nothing else).
#
# Usage: ./create-query-identity.sh -g <workspace-rg> [-w <workspace-name>] [-n <app-name>] [-y <secret-years>] [-o <file>] [-r]
# Writes <file> (default gpu-hours.query.env, mode 600, git-ignored) for query-gpu-hours.sh and the Azure SDKs.
# The secret is never printed. A rerun reuses the app, the role and the secret in <file>; -r adds a new secret.
# Needs: permission to create app registrations (or ownership of an app with this name) and Owner or
# User Access Administrator on the workspace.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: keep /subscriptions/... arguments unchanged
az() {
  if [[ -n "${GPUHOURS_SUBSCRIPTION_ID:-}" && "$1" != ad && "$1" != extension ]]; then
    command az "$@" --subscription "$GPUHOURS_SUBSCRIPTION_ID"
  else
    command az "$@"
  fi
}
clean() { tr -d '\r'; }
die() { echo "ERROR: $1" >&2; exit "${2:-1}"; }
usage() { sed -n '2,9p' "$0"; exit 1; }

RG=""; LAW="law-gpu-hours"; APP="gpu-hours-query"; YEARS=1; OUT="gpu-hours.query.env"; ROTATE=0
while getopts "g:w:n:y:o:rh" opt; do
  case $opt in
    g) RG=$OPTARG ;; w) LAW=$OPTARG ;; n) APP=$OPTARG ;; y) YEARS=$OPTARG ;; o) OUT=$OPTARG ;; r) ROTATE=1 ;;
    *) usage ;;
  esac
done
[[ -n "$RG" ]] || usage
[[ "$YEARS" =~ ^[1-9][0-9]*$ ]] || die "-y must be a whole number of years"

echo "==> workspace"
LAW_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query id -o tsv | clean)
WORKSPACE_GUID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query customerId -o tsv | clean)
TENANT_ID=$(az account show --query tenantId -o tsv | clean)
[[ -n "$LAW_ID" && -n "$WORKSPACE_GUID" && -n "$TENANT_ID" ]] || die "workspace $LAW not found in $RG"
echo "$LAW_ID"

echo "==> app registration $APP"
APP_IDS=$(az ad app list --display-name "$APP" --query "[].appId" -o tsv | clean)
case $(grep -c . <<<"$APP_IDS" || true) in
  0) APP_ID=$(az ad app create --display-name "$APP" --sign-in-audience AzureADMyOrg --query appId -o tsv | clean)
     echo "created app registration, client ID $APP_ID" ;;
  1) APP_ID=$APP_IDS; echo "reusing app registration, client ID $APP_ID" ;;
  *) die "several app registrations are named $APP; pass a unique name with -n" ;;
esac

echo "==> service principal"
SP_ID=$(az ad sp list --filter "appId eq '$APP_ID'" --query "[0].id" -o tsv | clean)
if [[ -z "$SP_ID" ]]; then
  SP_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv | clean)
  echo "created service principal, object ID $SP_ID"
else
  echo "reusing service principal, object ID $SP_ID"
fi

echo "==> Log Analytics Reader on the workspace (read-only)"
ASSIGNED=$(az role assignment list --assignee-object-id "$SP_ID" --role "Log Analytics Reader" --scope "$LAW_ID" \
  --query "length(@)" -o tsv | clean)
if [[ "$ASSIGNED" == 0 ]]; then
  # A new service principal can take a minute to replicate before a role can be assigned to it.
  for attempt in 1 2 3 4 5 6; do
    if az role assignment create --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal \
         --role "Log Analytics Reader" --scope "$LAW_ID" -o none; then
      echo "Log Analytics Reader granted"; break
    fi
    (( attempt < 6 )) || die "could not assign Log Analytics Reader; you need Owner or User Access Administrator on the workspace"
    echo "role assignment not accepted yet; retrying in 20 s"; sleep 20
  done
else
  echo "Log Analytics Reader already granted"
fi

echo "==> client secret"
KEEP=0
if [[ -f "$OUT" && "$ROTATE" == 0 ]] && grep -qx "AZURE_CLIENT_ID=$APP_ID" <(clean < "$OUT"); then
  KEEP=1
fi
if [[ "$KEEP" == 1 ]]; then
  echo "kept the secret already in $OUT (add -r to create a new one)"
else
  SECRET=$(az ad app credential reset --id "$APP_ID" --append --display-name gpu-hours-query --years "$YEARS" \
    --query password -o tsv 2>/dev/null | clean)
  [[ -n "$SECRET" ]] || die "could not create a client secret for $APP_ID"
  EXPIRES=$(az ad app credential list --id "$APP_ID" --query "max([].endDateTime)" -o tsv | clean)
  ( umask 077
    { echo "# GPU-hours query identity. Keep this file secret; it is git-ignored. Secret expires $EXPIRES."
      echo "AZURE_TENANT_ID=$TENANT_ID"
      echo "AZURE_CLIENT_ID=$APP_ID"
      echo "AZURE_CLIENT_SECRET=$SECRET"
      echo "WORKSPACE_GUID=$WORKSPACE_GUID"
    } > "$OUT" )
  chmod 600 "$OUT"
  unset SECRET
  echo "new secret written to $OUT (mode 600); it is not printed. Expires $EXPIRES"
fi

cat <<EOF

==> done
tenant ID     $TENANT_ID
client ID     $APP_ID
object ID     $SP_ID
workspace     $WORKSPACE_GUID
Test it (role assignments can take up to 5 minutes to apply):
  ./scripts/query-gpu-hours.sh -c $OUT -q kql/summary.kql -t PT1H
EOF
