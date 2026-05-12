"""Provision a Microsoft Entra Agent ID for our hosted agent.

Generated using the `entra-agent-id` skill from microsoft/skills.

What this script does (per the skill's 3-step workflow):
  Step 1: Create Agent Identity Blueprint (application object)
  Step 2: Create BlueprintPrincipal (mandatory — Blueprint does NOT auto-create SP)
  Step 3: Create Agent Identity instance for "hosted-agent-toolbox-demo"

CRITICAL warnings the skill enforces:
  - Agent Identity APIs are PREVIEW — only available under /beta
  - DefaultAzureCredential is REJECTED (azure CLI tokens have wrong scope → 403)
  - MUST use ClientSecretCredential or PowerShell Connect-MgGraph
  - Sponsors MUST be User objects (not SPs, not Groups)
  - BlueprintPrincipal step is MANDATORY — skipping = 400 on agent creation
  - All requests need OData-Version: 4.0 header

Source: https://github.com/microsoft/skills/blob/main/.github/skills/entra-agent-id/SKILL.md
        (fetched 2026-05-12)

Run:
    export AZURE_TENANT_ID=<your-tenant>
    export AZURE_CLIENT_ID=<dedicated-app-reg-client-id>
    export AZURE_CLIENT_SECRET=<dedicated-app-reg-secret>
    python provision_agent_identity.py
"""
import os
import subprocess
import sys
import time

import requests
from azure.identity import ClientSecretCredential

# ---- Required env (per skill spec) ----
TENANT = os.environ.get("AZURE_TENANT_ID")
CLIENT_ID = os.environ.get("AZURE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")

if not all([TENANT, CLIENT_ID, CLIENT_SECRET]):
    print("ERROR: AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET required.")
    print("       The skill explicitly forbids DefaultAzureCredential — use a dedicated app reg.")
    sys.exit(1)

# ---- Graph beta base URL (Agent ID is preview-only) ----
GRAPH = "https://graph.microsoft.com/beta"

# ---- Auth: client_credentials → Graph token ----
credential = ClientSecretCredential(tenant_id=TENANT, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
token = credential.get_token("https://graph.microsoft.com/.default").token

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "OData-Version": "4.0",  # REQUIRED for all Agent Identity API calls
}


def get_sponsor_user_id() -> str:
    """Sponsors MUST be User objects. Use az CLI to get current signed-in user."""
    result = subprocess.run(
        ["az", "ad", "signed-in-user", "show", "--query", "id", "-o", "tsv"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def create_blueprint(sponsor_user_id: str, display_name: str) -> dict:
    """Step 1: Create the Agent Identity Blueprint (application object)."""
    body = {
        "@odata.type": "Microsoft.Graph.AgentIdentityBlueprint",
        "displayName": display_name,
        "sponsors@odata.bind": [f"{GRAPH}/users/{sponsor_user_id}"],
    }
    r = requests.post(f"{GRAPH}/applications", headers=headers, json=body)
    r.raise_for_status()
    return r.json()


def create_blueprint_principal(app_id: str) -> dict:
    """Step 2 — MANDATORY. Without this, agent creation returns 400."""
    body = {
        "@odata.type": "Microsoft.Graph.AgentIdentityBlueprintPrincipal",
        "appId": app_id,
    }
    r = requests.post(f"{GRAPH}/servicePrincipals", headers=headers, json=body)
    r.raise_for_status()
    return r.json()


def create_agent_identity(blueprint_app_id: str, sponsor_user_id: str, instance_name: str) -> dict:
    """Step 3: Create an Agent Identity instance bound to the Blueprint."""
    body = {
        "@odata.type": "Microsoft.Graph.AgentIdentity",
        "displayName": instance_name,
        "agentIdentityBlueprintId": blueprint_app_id,
        "sponsors@odata.bind": [f"{GRAPH}/users/{sponsor_user_id}"],
    }
    r = requests.post(f"{GRAPH}/servicePrincipals", headers=headers, json=body)
    r.raise_for_status()
    return r.json()


def main():
    print("=" * 70)
    print("Provisioning Microsoft Entra Agent ID for hosted-agent-toolbox-demo")
    print("=" * 70)

    sponsor_id = get_sponsor_user_id()
    print(f"Sponsor user: {sponsor_id}")

    # --- Step 1 ---
    print("\n[Step 1] Creating Agent Identity Blueprint...")
    blueprint = create_blueprint(sponsor_id, "hosted-agent-toolbox-demo-blueprint")
    app_id = blueprint["appId"]
    print(f"  ✅ Blueprint appId={app_id} objectId={blueprint['id']}")

    # --- Step 2 (MANDATORY per skill warning) ---
    print("\n[Step 2] Creating BlueprintPrincipal (mandatory!)...")
    sp = create_blueprint_principal(app_id)
    print(f"  ✅ BlueprintPrincipal id={sp['id']}")
    time.sleep(5)  # let it propagate

    # --- Step 3 ---
    print("\n[Step 3] Creating Agent Identity instance...")
    agent = create_agent_identity(app_id, sponsor_id, "hosted-agent-toolbox-demo-instance-1")
    print(f"  ✅ Agent Identity id={agent['id']} appId={agent['appId']}")

    print("\n" + "=" * 70)
    print("Result: hosted-agent-toolbox-demo now has an OAuth2-capable Entra identity.")
    print("        Use agent['id'] as the SP object ID for Azure RBAC assignments.")
    print("=" * 70)


if __name__ == "__main__":
    main()
