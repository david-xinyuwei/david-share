# foundry-iq-knowledge-bases Skill — Live Demo

> Sub-skill of [microsoft-foundry](https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry).

## Triple

| Item | Value |
|------|-------|
| **How we tested it** | Configured the `file_search` Toolbox tool (which uses Foundry IQ vector store knowledge base) to ground our agent responses on uploaded documents — equivalent to the agentic retrieval pipeline the skill describes. |
| **Prompt key constraint** | "Use Foundry vector store API (POST {project_endpoint}/openai/v1/vector_stores) — NOT raw Azure AI Search; permission-aware grounding via the project's RBAC; multi-source via file_search tool in Toolbox." |
| **Deliverable** | Live `file_search` integration in our hosted agent — agent retrieves from Foundry-managed vector store via the Toolbox `agent-tools` endpoint. Doc upload via portal or REST API. Verification: when our demo is asked "what does the doc say about X", agent uses `file_search` and returns grounded answer with citations. |

## Reproducible prompt

> ```
> Using the foundry-iq-knowledge-bases skill, configure permission-aware document
> grounding for the hosted-agent-toolbox-demo agent.
>   1. Use Foundry vector store API: POST {project_endpoint}/openai/v1/vector_stores
>   2. Reference the vector store IDs in FILE_SEARCH_VECTOR_STORE_IDS env var.
>   3. Connect via the Toolbox `file_search` built-in tool — NOT raw AI Search calls.
>   4. Permission inheritance: the project's RBAC governs document access.
>   5. Multi-source support — list multiple vector store IDs comma-separated.
> Output: Wire-up in agent code + .env documenting FILE_SEARCH_VECTOR_STORE_IDS
> ```

## Skill rules enforced

- ✅ Use Foundry's managed vector store (NOT direct AI Search calls)
- ✅ Permission-aware (relies on project's RBAC, not document-level ACL)
- ✅ Toolbox `file_search` integration (one MCP endpoint, no separate config)
- ✅ Multi-source via comma-separated vector store IDs

## Excerpt from .env.example

```bash
# Optional: file_search vector store IDs (comma-separated).
# Create a vector store first via POST {project_endpoint}/openai/v1/vector_stores.
FILE_SEARCH_VECTOR_STORE_IDS=
```

## Source

- Sub-skill: https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry (IQ knowledge bases sub-section)
- Verified deployment: `Foundry-Hosted-Agent-Toolbox-Demo/.env.example` + `main.py`
- Foundry vector store API: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/api-reference
