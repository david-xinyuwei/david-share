# Troubleshooting

## `401 Unauthorized` From Toolbox MCP

Likely causes:

- Wrong Azure tenant or subscription in local CLI.
- Missing RBAC on the Foundry project.
- Missing `Foundry-Features: Toolboxes=V1Preview` header.
- Token acquired for the wrong resource.

Fix:

```bash
az account show
az account set --subscription <subscription-id>
```

Keep `AZURE_AUTH_MODE=cli` for local multi-tenant work. The scripts request tokens for `https://ai.azure.com/.default` and include the preview header.

## `prompts/list` Or Prompt Loading Errors

Foundry Toolbox MCP endpoint may not implement MCP prompt listing. Keep this in `main.py` and tests:

```python
load_prompts=False
```

## Toolbox `web_search` Lists But Invoke Fails

Symptom:

```text
DeploymentNotFound
```

MCP tool listing only proves the tool is advertised. It does not prove the preview runtime path can invoke it in every project. This repo uses `direct_web_search` for runtime public web search because the Azure AI Foundry OpenAI Web Search docs describe the Responses API path:

```json
{"tools": [{"type": "web_search"}]}
```

Source: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/web-search

## `ModuleNotFoundError: main`

Run scripts from the repo root:

```bash
python scripts/smoke_test.py
```

`scripts/smoke_test.py` adds the repo root to `sys.path`, but running from unusual working directories can still confuse relative paths in shells or IDEs.

## Missing Environment Variable

Compare `.env` with `.env.example`:

```bash
FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4-1-mini
TOOLBOX_NAME=agent-tools
AZURE_AUTH_MODE=cli
ENABLE_DIRECT_WEB_SEARCH=true
```

## DNS Or Endpoint Shape Issues

Use a Foundry project endpoint in this shape:

```text
https://<account>.services.ai.azure.com/api/projects/<project>
```

The Toolbox consumer MCP endpoint is then:

```text
https://<account>.services.ai.azure.com/api/projects/<project>/toolboxes/<toolbox-name>/mcp?api-version=v1
```

## HTTP Server Starts But Test Hangs

Check that `main.py` is still running and listening on the expected port:

```bash
curl http://localhost:8088/
```

The root path may not return a useful app page; the important endpoint is `/responses`.

If another process already uses `8088`, set a different port:

```bash
PORT=8090 python main.py
python scripts/http_smoke_test.py --base-url http://localhost:8090
```

## OAuth Consent Required

OAuth-backed MCP tools can return consent-required errors such as `-32006`. Complete user consent for the backing connection and retry. Keep this separate from service-to-service managed identity flows.

## Local Test Works But Hosted Deployment Fails

Check:

- The hosted agent identity has `Azure AI User` on the Foundry project.
- Environment variables in `agent.yaml` are set in the hosted runtime.
- The toolbox name exists in the same Foundry project.
- The container image does not depend on local `.env` files.