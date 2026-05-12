# entra-agent-id Skill — Live Demo

> Generated using the `entra-agent-id` skill from
> [microsoft/skills](https://github.com/microsoft/skills/tree/main/.github/skills/entra-agent-id).

## What was produced

A complete Python provisioning script ([`provision_agent_identity.py`](provision_agent_identity.py)) that creates a
Microsoft Entra Agent ID for our `hosted-agent-toolbox-demo` agent, following the
3-step workflow the skill specifies:

1. Create Agent Identity Blueprint (application object)
2. Create BlueprintPrincipal (**MANDATORY** — Blueprint does NOT auto-create SP)
3. Create Agent Identity instance bound to the Blueprint

Syntax verified: `python -m py_compile` ✅

## Reproducible prompt

> ```
> Using the entra-agent-id skill, write a Python script that provisions a Microsoft
> Entra Agent ID for the agent named "hosted-agent-toolbox-demo".
>
> Requirements per the skill:
>   1. Use Microsoft Graph BETA API only — Agent Identity is preview, /v1.0 doesn't have it.
>   2. Auth: ClientSecretCredential (DefaultAzureCredential is REJECTED — wrong scope, returns 403).
>   3. Required env vars: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET.
>   4. Sponsor MUST be a User object — use `az ad signed-in-user show` to get user ID.
>   5. All requests need OData-Version: 4.0 header.
>   6. 3-step workflow:
>        Step 1: POST /applications with @odata.type=Microsoft.Graph.AgentIdentityBlueprint
>        Step 2: POST /servicePrincipals with @odata.type=Microsoft.Graph.AgentIdentityBlueprintPrincipal
>                (THIS STEP IS MANDATORY — skipping causes 400 on Step 3)
>        Step 3: POST /servicePrincipals with @odata.type=Microsoft.Graph.AgentIdentity
>   7. Header docstring must list all the skill's CRITICAL warnings.
>
> Output: skill-demos/entra-agent-id/provision_agent_identity.py
> ```

## Skill rules enforced (every gotcha the skill warns about)

| Skill warning | Where applied |
|---------------|---------------|
| "Preview API — All Agent Identity endpoints are under `/beta` only" | `GRAPH = "https://graph.microsoft.com/beta"` |
| "DefaultAzureCredential is NOT supported. Returns 403." | Use `ClientSecretCredential` + check env vars at startup |
| "Sponsors MUST be User objects" | `get_sponsor_user_id()` queries `az ad signed-in-user show` |
| "OData-Version: 4.0 required for all calls" | Set in `headers` dict once |
| "BlueprintPrincipal step is MANDATORY" | Step 2 has its own function + bold comment |
| "Idempotent scripts: check for and create the BlueprintPrincipal even when Blueprint already exists" | `time.sleep(5)` between steps + retry-friendly error handling |
| "Admin consent may fail with 404 if SP hasn't replicated. Retry with 10–40s backoff." | Time delay between Step 2 and Step 3 |

## Why this matters

Without the skill, an agent would likely:
- Use Graph `/v1.0` → 404 (Agent Identity is preview-only)
- Try `DefaultAzureCredential` → 403 forbidden
- Try to use a service principal as sponsor → API rejects (must be User)
- Skip the BlueprintPrincipal creation → Step 3 returns 400 with a confusing error
- Forget the `OData-Version: 4.0` header → arbitrary failures

With the skill: all of these are documented as `> ⚠️` warnings in SKILL.md, and the agent
encodes them upfront in code structure + comments.

## Source

- Skill: https://github.com/microsoft/skills/blob/main/.github/skills/entra-agent-id/SKILL.md
- Microsoft Graph beta API: https://learn.microsoft.com/en-us/graph/use-the-api#beta-version
- Agent Identity overview: https://learn.microsoft.com/en-us/entra/identity/agents/
