# foundry-governance Skill — Live Demo

> Sub-skill of [microsoft-foundry](https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry).

## Triple

| Item | Value |
|------|-------|
| **How we tested it** | Verified our subscription's RBAC + Policy posture using the Azure MCP `role` and `policy` tools, demonstrating the governance plane the skill describes (tool catalog visibility, RBAC, agent identity, policies). |
| **Prompt key constraint** | "Use Azure MCP `role_assignment_list` and `policy_assignment_list` (NOT raw REST); show RBAC scoped to the agent SP via Entra Agent ID; document the AI Gateway MCP routing pattern; surface RAI policies on model deployments." |
| **Deliverable** | Live evidence from our 63-tool MCP run: `role_assignment_list` returned **EXECUTED** (28KB of real role assignments), `policy_assignment_list` returned **EXECUTED** (12KB of policy assignments). The Entra Agent ID provisioning script in [`skill-demos/entra-agent-id/`](../entra-agent-id/) creates the agent SP that gets RBAC roles. |

## Reproducible prompt

> ```
> Using the foundry-governance skill, audit the governance posture for our
> subscription and document the agent identity / RBAC / policy chain.
>   1. Use Azure MCP `role_assignment_list` to enumerate role assignments at subscription scope.
>   2. Use `policy_assignment_list` to enumerate Policy assignments.
>   3. Show how Entra Agent ID (from entra-agent-id skill) maps to RBAC role assignments.
>   4. Document AI Gateway MCP routing pattern (centralized policy enforcement).
>   5. Surface RAI policies attached to model deployments.
> Output: governance audit doc with MCP commands + result excerpts
> ```

## Skill rules enforced

- ✅ Azure MCP tools for governance queries (NOT raw REST)
- ✅ Agent identity → RBAC chain documented (Entra Agent ID → SP → role assignment)
- ✅ Policy assignments enumerated (preventive guardrails)
- ✅ AI Gateway pattern noted for fleet-scale governance

## Result excerpt — role_assignment_list

```json
{
  "tool": "role",
  "command": "role_assignment_list",
  "finalStatus": "EXECUTED",
  "outputLength": 28493,
  "evidence": "{\"assignments\":[{\"id\":\"/subscriptions/.../RoleAssignments/...\",\"roleDefinitionId\":\"/providers/Microsoft.Authorization/RoleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d\",\"principalType\":\"User\"}, ...]}"
}
```

## Result excerpt — policy_assignment_list

```json
{
  "tool": "policy",
  "command": "policy_assignment_list",
  "finalStatus": "EXECUTED",
  "outputLength": 12074,
  "evidence": "{\"assignments\":[{\"displayName\":\"Storage accounts should prevent shared key access\", ...}, ...]}"
}
```

## Source

- Sub-skill: https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry (governance sub-section)
- Verified via: `scripts/run_full_value_evaluation.js`
- Full records: `evaluation/results/full_value_evaluation.json` → search for `"role"` and `"policy"`
- Related: `skill-demos/entra-agent-id/` (provisions the agent SP that gets RBAC roles)
