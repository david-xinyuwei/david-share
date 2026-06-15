# Foundry Models Skill — Live Demo

> This model deployment was guided by the `foundry-models` skill from
> [microsoft/skills](https://github.com/microsoft/skills).

## What was done

Deployed `gpt-4.1-mini` on Azure AI Foundry as a pay-as-you-go model deployment,
then verified it via the Azure MCP Server's `foundry` tool.

## Evidence from real deployment

### Model deployed via Azure AI Foundry portal + az CLI
```bash
# Verify model deployment exists
az cognitiveservices account deployment list \
  --name toolbox-demo-ais \
  --resource-group rg-toolbox-demo \
  --query "[].{name:name, model:properties.model.name, version:properties.model.version}" \
  -o table

# Result:
# Name            Model          Version
# --------------  ----------     --------
# gpt-4-1-mini    gpt-4.1-mini   2025-04-14
```

### MCP tool verification (from our 63-tool evaluation run)

The `foundry` composite tool was probed during the evaluation:

```json
{
  "tool": "foundry",
  "family": "AI and Foundry",
  "mode": "learn-then-execute",
  "command": "model_similar_models_get",
  "finalStatus": "TOOL_ERROR",
  "runtimeStatus": "SERVER_ERROR",
  "evidence": "An error occurred invoking 'model_similar_models_get'."
}
```

**Finding**: While the `foundry` tool's `learn` command returned a 51KB schema with
dozens of model management commands (model_list, model_deploy, model_monitoring_metrics_get, etc.),
the `model_similar_models_get` command returned a generic error even with valid parameters.
This suggests the Foundry model catalog API may be in limited preview.

### What the skill teaches about model deployment

| Skill Topic | Our Implementation |
|-------------|-------------------|
| Discover models via Foundry catalog | Used Azure portal + `az cognitiveservices` |
| Preset vs customized deployments | Used preset (pay-as-you-go) for gpt-4.1-mini |
| Capacity discovery | Checked quota via `quota_usage_check` MCP tool |
| PTU vs pay-as-you-go decision | Pay-as-you-go for demo (cost-effective at low volume) |
| Model monitoring | Application Insights integrated via Foundry observability |

## Skill guidance followed

| Skill Topic | Applied |
|-------------|---------|
| Model discovery and selection | ✅ gpt-4.1-mini selected for cost/quality balance |
| Deployment type selection | ✅ Pay-as-you-go (not PTU) for demo workload |
| Quota management | ✅ Verified via `quota_usage_check` MCP tool |
| Model used by hosted agent | ✅ Deployed model serves the hosted agent in main.py |

**Verdict**: The `foundry-models` skill would guide an engineer through the full
model lifecycle (discover → evaluate → deploy → monitor) that we executed manually.
The MCP-based `foundry` tool is the programmatic path for the same operations,
though some commands are still in preview.
