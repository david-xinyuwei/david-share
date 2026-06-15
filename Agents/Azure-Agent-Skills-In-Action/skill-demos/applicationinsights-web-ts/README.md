# applicationinsights-web-ts Skill — Live Demo

> Generated using the `applicationinsights-web-ts` skill from
> [microsoft/skills](https://github.com/microsoft/skills/tree/main/.github/skills/applicationinsights-web-ts).

## What was produced

A drop-in TypeScript module ([`appInsights.ts`](appInsights.ts)) that adds Application Insights
browser instrumentation to the Foundry-Hosted-Agent-Toolbox-Demo dashboard. It includes:

- Page view + AJAX/fetch auto-tracking
- W3C distributed tracing (browser ↔ FastAPI backend correlation)
- Click Analytics plugin
- Telemetry initializer that scrubs `token=`/`access_token=` from URLs
- Filters out the `/api/health` polling noise
- **GenAI agent semantic-convention tracking** for every agent invocation

## Reproducible prompt

Load the `applicationinsights-web-ts` skill and use this prompt:

> ```
> Using the applicationinsights-web-ts skill, generate a TypeScript instrumentation
> module for a browser SPA (Foundry Demo dashboard at app/static/index.html) that:
>
>   1. Uses @microsoft/applicationinsights-web (NOT @azure/monitor-opentelemetry — that's Node).
>   2. Connection string from env (VITE_APPINSIGHTS_CONNECTION_STRING).
>      WARN that connection strings ship in plaintext to clients — recommend a
>      separate App Insights resource.
>   3. distributedTracingMode: 2 (AI_AND_W3C) so traceparent reaches FastAPI backend.
>   4. Telemetry initializer that:
>        - Tags ai.cloud.role = "foundry-demo-ui"
>        - Drops PageviewData where uri ends with /api/health
>        - Scrubs token=/sig=/key=/access_token= query-string secrets
>   5. ClickAnalyticsPlugin enabled with data-ai-* attributes.
>   6. Add helpers trackAgentInvocation() and trackToolCall() that emit
>      OpenTelemetry GenAI semantic-convention attributes:
>        - gen_ai.system, gen_ai.operation.name, gen_ai.agent.{name,id}
>        - gen_ai.usage.{input,output,total}_tokens
>        - gen_ai.request.model
>   7. Show how to wire trackAgentInvocation() into the existing sendChat() function.
>
> Output: skill-demos/applicationinsights-web-ts/appInsights.ts
> ```

## Skill guidance enforced (verbatim from SKILL.md)

| Skill rule | Where applied in our code |
|------------|--------------------------|
| "It ships in plaintext to clients — Microsoft Entra ID auth is not supported for browser telemetry. Use a separate App Insights resource" | Header comment + recommendation in module docstring |
| "Set `distributedTracingMode: 2`" | `config.distributedTracingMode: 2` |
| "Run for every envelope before send. Return `false` to drop." | `addTelemetryInitializer` returns `false` for `/api/health` |
| "Scrub query-string secrets" | regex on `(token\|sig\|key\|access_token)=` |
| "Mark elements with `data-ai-*` attributes; clicks are emitted as Custom Events" | ClickAnalytics with `customDataPrefix: "data-ai-"` |
| OTel GenAI semantic conventions for agent/tool/model spans | `trackAgentInvocation()` emits `gen_ai.system`, `gen_ai.agent.*`, `gen_ai.usage.*` |

## Why this matters

Without the skill, an agent would likely:
- Use `@azure/monitor-opentelemetry` (the Node.js server SDK) by mistake — wrong package
- Forget the W3C trace context flag → backend correlation breaks
- Send the connection string secret unredacted in URLs
- Miss the OTel GenAI semantic convention names that App Insights uses to identify agent traffic

With the skill: the agent automatically picks the right SDK, follows official patterns, and matches
the conventions Foundry observability tooling expects to see.

## Source

- Skill: https://github.com/microsoft/skills/blob/main/.github/skills/applicationinsights-web-ts/SKILL.md
- Official SDK: https://learn.microsoft.com/en-us/azure/azure-monitor/app/javascript-sdk
- OTel GenAI conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
