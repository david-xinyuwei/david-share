# Demo Script

This is a short customer-neutral demo flow for showing why Hosted Agent + Toolbox is useful.

## Demo Goal

Show that one cloud-side agent endpoint can orchestrate both:

- governed shared tools from a Foundry Toolbox, and
- current public web search through the Foundry Responses API.

## Setup Check

Run these before the meeting:

```bash
python scripts/repo_check.py
python scripts/verify_toolbox.py --endpoint "$TOOLBOX_MCP_ENDPOINT"
python scripts/smoke_test.py
```

Expected result:

- `repo_check.py` prints `PASS` entries.
- `verify_toolbox.py` lists `code_interpreter`.
- `smoke_test.py` prints `WEB_RESULT_START/END` and `CODE_RESULT_START/END`.

## Live Demo Flow

### 1. Show the architecture

Open [docs/architecture.md](architecture.md) and explain:

- Hosted Agent is the stable endpoint.
- Toolbox is the managed tool catalog.
- Direct `web_search` is used for current public web facts.

### 2. Start the local Responses server

```bash
python main.py
```

Say: this is the same host code that can be containerized and deployed as a Hosted Agent.

### 3. Invoke Code Interpreter through Toolbox

```bash
curl -X POST http://localhost:8088/responses \
  -H "Content-Type: application/json" \
  --data @examples/requests/code_interpreter.json
```

Expected answer: the agent should calculate that the sum of squares from 1 to 5 is `55`.

Message to audience: this validates that the agent can call a governed shared tool through Toolbox MCP.

### 4. Invoke Direct Web Search

```bash
curl -X POST http://localhost:8088/responses \
  -H "Content-Type: application/json" \
  --data @examples/requests/direct_web_search.json
```

Expected answer: the agent should summarize Microsoft Foundry Toolbox or the requested public web topic.

Message to audience: this keeps web grounding on the documented Responses API path while Toolbox focuses on managed tools.

### 5. Explain the extension point

Replace the sample tools with real tools:

| Demo tool | Real-world replacement |
| --- | --- |
| `code_interpreter` | telemetry analysis, policy checks, diagnostics, data transforms |
| `direct_web_search` | public docs lookup, release notes lookup, market/news lookup |
| custom MCP tool | internal API, device capability, game service, CI/CD system |

## Closing Message

This is not a final business workflow. It is the minimal host-agent and tool-catalog skeleton that a team can extend into its own scenario-specific tools.