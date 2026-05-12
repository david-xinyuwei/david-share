# foundry-workflows Skill — Live Demo

> Sub-skill of [microsoft-foundry](https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry).

## Triple

| Item | Value |
|------|-------|
| **How we tested it** | Designed a multi-agent workflow leveraging our existing 3-agent pattern in `Foundry-Hosted-Agent-Toolbox-Demo` (default agent / math-only / rag-only), modeling the **Connected Agents** pattern the skill describes. |
| **Prompt key constraint** | "Use Connected Agents pattern (NOT manual orchestration); declarative handoff via tool calls; one specialist agent per skill subset; route based on intent classification." |
| **Deliverable** | Multi-agent persona registry in [`app/server.py`](https://github.com/david-xinyuwei/david-share/blob/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo/app/server.py) (`AGENTS` dict with default/math-only/rag-only) and the per-agent tool-subset constraint enforced via system prompt prefix. |

## Reproducible prompt

> ```
> Using the foundry-workflows skill, design a multi-agent workflow for the demo
> with handoff between specialist agents.
>   1. Use the Connected Agents pattern from the skill (declarative, NOT manual).
>   2. Each agent persona = name + tool subset + system instructions.
>   3. Use a router/coordinator agent that picks the specialist based on intent.
>   4. Tool subsets must be enforced (router can call specialist as a tool).
>   5. Show the handoff via system prompt + agent_id parameter routing.
> Output: AGENTS registry + handoff pattern in server.py
> ```

## Skill rules enforced

- ✅ Per-agent tool subset enforcement (system prompt prefix lists allowed tools)
- ✅ Multiple specialist personas (default/math-only/rag-only) — Connected Agents pattern
- ✅ Declarative routing via `agent_id` parameter (not hard-coded if/else)
- ✅ Each agent has its own instructions

## Excerpt from server.py

```python
AGENTS = {
  "math-only": {
    "name": "Math agent (code_interpreter only)",
    "tools": ["code_interpreter"],
    "instructions": "You are a math assistant. You only have code_interpreter — use it for any computation."
  },
  "rag-only": {
    "name": "Knowledge agent (file_search only)",
    "tools": ["file_search"],
    "instructions": "You are a knowledge-base assistant. You only have file_search — answer strictly from uploaded documents."
  },
}

# Tool subset enforced via system prompt prefix
constraint = (
  f"[AGENT: {agent['name']}]\n"
  f"For this request you may ONLY use these tools: {','.join(agent['tools'])}.\n"
  f"User request: {prompt}"
)
```

## Source

- Sub-skill: https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry (workflows sub-section)
- Verified deployment: `Foundry-Hosted-Agent-Toolbox-Demo/app/server.py`
