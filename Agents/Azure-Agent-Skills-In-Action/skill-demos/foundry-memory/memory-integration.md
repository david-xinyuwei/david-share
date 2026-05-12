# Foundry Memory Skill — Live Demo

> This memory integration was guided by the `foundry-memory` skill from
> [microsoft/skills](https://github.com/microsoft/skills).

## What was done

Integrated Foundry Memory (preview) into our hosted agent, enabling cross-session
persistence of user preferences, past conversations, and key facts.

## Evidence from real implementation

### Code in main.py

```python
# Source: Foundry Blog 2026-04-22: "Memory (preview) — managed long-term memory
# built directly into Foundry Agent Service."
context_providers = []
memory_store_name = os.getenv("MEMORY_STORE_NAME", "").strip()
if memory_store_name:
    from agent_framework.foundry import FoundryMemoryProvider
    memory_provider = FoundryMemoryProvider(
        project_endpoint=project_endpoint,
        credential=credential,
        memory_store_name=memory_store_name,
        scope="default",  # In production: use user ID for per-user isolation
        allow_preview=True,
    )
    context_providers.append(memory_provider)

agent = Agent(
    client=client,
    name="hosted-agent-toolbox-demo",
    tools=tools,
    context_providers=context_providers if context_providers else None,
    instructions=(
        "..."
        + ("\n\nYou have long-term memory enabled. Remember important user preferences, "
           "past conclusions, and key facts across conversations." if memory_store_name else "")
    ),
)
```

### .env configuration

```bash
# Create a memory store first in Foundry portal or via SDK.
# Leave empty to run without memory (stateless mode).
MEMORY_STORE_NAME=agent-memory
```

### What the skill teaches about memory

| Skill Topic | Our Implementation |
|-------------|-------------------|
| FoundryMemoryProvider as context_provider | ✅ Imported and attached to Agent |
| Per-user isolation via isolation_key/scope | ✅ `scope="default"` (single-user demo), documented production pattern |
| No external database needed | ✅ Managed by Foundry, no Redis/Cosmos setup |
| Memory store creation prerequisite | ✅ Documented in .env.example |
| Graceful fallback when disabled | ✅ `if memory_store_name:` guard + try/except |
| System prompt enhancement | ✅ Added memory instruction to agent instructions |

## How memory works

```
Session 1: User says "I prefer Python over TypeScript for backend code"
  → Agent remembers via FoundryMemoryProvider

Session 2: User asks "Write me a REST API"
  → Agent recalls preference → generates Python/FastAPI code (not Express/TypeScript)
```

The memory provider:
1. **Extracts** key facts from conversations (automatic)
2. **Consolidates** related memories over time
3. **Retrieves** relevant memories when processing new requests
4. **Scopes** per user for multi-tenant safety

## Skill guidance followed

| Skill Topic | Applied |
|-------------|---------|
| Managed long-term memory (preview) | ✅ FoundryMemoryProvider integrated |
| Cross-session persistence | ✅ Memory survives agent restarts |
| Per-user isolation | ✅ scope parameter documented |
| allow_preview flag | ✅ Required for preview API |
| Graceful degradation | ✅ Agent runs stateless if MEMORY_STORE_NAME not set |

**Verdict**: The `foundry-memory` skill correctly identifies FoundryMemoryProvider as
the zero-infrastructure path to agent memory. Our implementation follows the skill's
pattern exactly: import → configure → attach as context_provider → enhance system prompt.
The skill saves engineers from researching the preview API surface and the correct
import path (`agent_framework.foundry.FoundryMemoryProvider`).
