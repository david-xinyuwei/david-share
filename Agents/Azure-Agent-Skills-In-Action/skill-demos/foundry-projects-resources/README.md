# foundry-projects-resources Skill — Live Demo

> Sub-skill of [microsoft-foundry](https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry).

## Triple

| Item | Value |
|------|-------|
| **How we tested it** | Provisioned the Foundry project + AI Services account that hosts our `hosted-agent-toolbox-demo` agent, configured project connections (managed identity), and verified via the MCP `foundry` tool from our 63-tool run. |
| **Prompt key constraint** | "Use `azd up` with infra/main.bicep; AI Services account in same RG; project_endpoint format `https://<resource>.services.ai.azure.com/api/projects/<project>`; managed identity for connections (NOT keys)." |
| **Deliverable** | Real provisioned resources: AI Services `toolbox-demo-ais` + Foundry project + project connection (managed identity). Bicep templates in [`Foundry-Hosted-Agent-Toolbox-Demo/infra/`](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo/infra). MCP verification: `subscription_list` + `group_resource_list` returned the live resources (see `evaluation/results/full_value_evaluation.json`). |

## Reproducible prompt

> ```
> Using the foundry-projects-resources skill, provision the infrastructure for
> a Foundry hosted agent named hosted-agent-toolbox-demo. Requirements:
>   1. Use `azd up` with infra/main.bicep — NOT manual portal clicks.
>   2. AI Services (Cognitive Services) account in the same resource group.
>   3. Foundry project endpoint format: https://<resource>.services.ai.azure.com/api/projects/<project>
>   4. Use Managed Identity for connections, NOT keys.
>   5. Output FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_AGENT_ID to .env.
> Output: infra/main.bicep + .env.example with the right shape
> ```

## Skill rules enforced

- ✅ `azd up` for end-to-end provisioning (not manual)
- ✅ Managed identity for connections (no keys)
- ✅ Project endpoint format compliance
- ✅ Co-located AI Services account + project in one RG

## Source

- Sub-skill: https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry/project
- Verified deployment: `Foundry-Hosted-Agent-Toolbox-Demo/`
- MCP verification: see `evaluation/results/full_value_evaluation.json` records for `subscription_list` and `group_resource_list`
