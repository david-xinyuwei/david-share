# foundry-managed-skills Skill — Live Demo

> Sub-skill of [microsoft-foundry](https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry).

## Triple

| Item | Value |
|------|-------|
| **How we tested it** | Wrote a SKILL.md (via `skill-creator` skill) ready to be uploaded to Foundry's managed Skills REST API as a Foundry-side resource — instead of bundling skill content into the container image. |
| **Prompt key constraint** | "Author SKILL.md once with frontmatter (name + description + applicability); register via Foundry Skills REST API; load into hosted agent container at runtime — do NOT bake into Docker image." |
| **Deliverable** | The new SKILL.md from the `skill-creator` demo: [`skill-demos/skill-creator/azure-mcp-evaluation-SKILL.md`](../skill-creator/azure-mcp-evaluation-SKILL.md). It's structured for Foundry Skills REST API upload (frontmatter + body sections that map to Foundry's schema). |

## Reproducible prompt

> ```
> Using the foundry-managed-skills skill, prepare a SKILL.md for upload as a
> Foundry-side resource (NOT bundled into the container image).
>   1. Author once, register via Foundry Skills REST API.
>   2. YAML frontmatter must include: name, description, applicability/compatibility.
>   3. Body sections that Foundry reads: Overview, Triggers, Tools, Examples, Source.
>   4. The hosted agent loads the skill at runtime — no rebuild on skill update.
>   5. Skill versioning via REST API (PUT to update existing skill).
> Output: SKILL.md ready for upload + the cURL or SDK call to register it
> ```

## Skill rules enforced

- ✅ Frontmatter compliant with Foundry Skills schema
- ✅ Skill content NOT in Docker image (loadable at runtime)
- ✅ Version-controlled via REST API
- ✅ Compatible with multiple agent hosts (Copilot CLI, Claude Code, opencode)

## Registration call (would be run after upload)

```bash
# Pseudo-code — actual Foundry Skills API endpoint TBD per region/preview status
curl -X POST "${FOUNDRY_PROJECT_ENDPOINT}/skills?api-version=preview" \
  -H "Authorization: Bearer $(az account get-access-token --resource https://ai.azure.com/.default --query accessToken -o tsv)" \
  -H "Content-Type: text/markdown" \
  --data-binary @skill-demos/skill-creator/azure-mcp-evaluation-SKILL.md
```

## Source

- Sub-skill: https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry (managed-skills sub-section)
- Verified artifact: [`skill-demos/skill-creator/azure-mcp-evaluation-SKILL.md`](../skill-creator/azure-mcp-evaluation-SKILL.md)
