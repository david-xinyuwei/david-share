# foundry-extensions Skill — Live Demo

> Sub-skill of [microsoft-foundry](https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry).

## Triple

| Item | Value |
|------|-------|
| **How we tested it** | Verified the `foundryextensions` MCP composite tool against our Foundry project and confirmed which preview commands work and which require additional resources. |
| **Prompt key constraint** | "List foundryextensions sub-commands via `learn`; identify SCHEMA_VERIFIED vs EXECUTED items; document required preview-only inputs (endpoint parameter)." |
| **Deliverable** | Tool verification record from our 63-tool MCP run: `foundryextensions_knowledge_index_list` returned **SCHEMA_VERIFIED** with 7 command specs because it needed an `endpoint` parameter we didn't have a Knowledge Index for. Full record in [`evaluation/results/full_value_evaluation.json`](../../evaluation/results/full_value_evaluation.json). |

## Reproducible prompt

> ```
> Using the foundry-extensions skill, verify which Foundry Extensions APIs are
> callable via the Azure MCP `foundryextensions` composite tool.
>   1. Send {"command": "learn"} to discover sub-commands.
>   2. For each sub-command, identify required parameters.
>   3. Mark schema-verified vs requires-resource vs server-error.
>   4. Document the endpoint format for Knowledge Index endpoints.
> Output: Verification record showing which commands need which inputs.
> ```

## Skill rules enforced

- ✅ Used `learn` step (skill mandatory pattern for composite tools)
- ✅ Documented missing inputs honestly (didn't fake resource availability)
- ✅ Recorded as SCHEMA_VERIFIED in eval matrix (not EXECUTED, not FAILED)

## Result excerpt

```json
{
  "tool": "foundryextensions",
  "command": "foundryextensions_knowledge_index_list",
  "finalStatus": "SCHEMA_VERIFIED",
  "missingRequired": ["endpoint"],
  "evidence": "Schema verified (7 command specs); required inputs not available in this subscription harness: endpoint."
}
```

## Source

- Sub-skill: https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry (extensions sub-section)
- Verified via: `scripts/run_full_value_evaluation.js`
- Full record: `evaluation/results/full_value_evaluation.json` → search for `"foundryextensions"`
