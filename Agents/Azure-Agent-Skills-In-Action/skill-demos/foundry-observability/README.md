# foundry-observability Skill — Live Demo

> Sub-skill of [microsoft-foundry](https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry).

## Triple

| Item | Value |
|------|-------|
| **How we tested it** | Wired App Insights AppTraces + AppEvents to monitor our hosted agent end-to-end (frontend → FastAPI → Foundry) using **OpenTelemetry GenAI traces**, then wrote 7 KQL queries to surface the data — fulfilling the skill's "trace, monitor, evaluate Foundry hosted agents end-to-end" mandate. |
| **Prompt key constraint** | "OpenTelemetry GenAI traces in App Insights; eval-trace correlation via operation_Id (W3C trace_id); batch evals + regression detection; surface via KQL queries (NOT Azure portal clicks)." |
| **Deliverable** | Three coordinated artifacts: (1) browser-side OTel GenAI tracking in [`skill-demos/applicationinsights-web-ts/appInsights.ts`](../applicationinsights-web-ts/appInsights.ts); (2) backend `/api/agent-logs` endpoint in [`Foundry-Hosted-Agent-Toolbox-Demo/app/server.py`](https://github.com/david-xinyuwei/david-share/blob/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo/app/server.py); (3) 7 production KQL queries in [`skill-demos/kql/agent-monitoring.kql`](../kql/agent-monitoring.kql). |

## Reproducible prompt

> ```
> Using the foundry-observability skill, set up end-to-end observability for
> hosted-agent-toolbox-demo across browser → FastAPI → Foundry.
>   1. OpenTelemetry GenAI semantic conventions for ALL agent spans:
>        gen_ai.system, gen_ai.agent.name, gen_ai.agent.id,
>        gen_ai.usage.{input,output,total}_tokens, gen_ai.request.model
>   2. W3C distributed tracing — browser distributedTracingMode: 2 (AI_AND_W3C),
>      backend reads traceparent header → emits correlated OTel spans.
>   3. App Insights as the sink (separate resource for browser RUM).
>   4. KQL queries for: agent-by-agent invocation count, p50/p95/p99 latency,
>      error rate per hour, token consumption per model, cross-table trace correlation.
>   5. Eval-trace correlation: link evaluation runs to the underlying agent operation_Id.
> Output: browser instrumentation + backend log endpoint + 7 KQL queries
> ```

## Skill rules enforced

- ✅ OTel GenAI semantic conventions (canonical attribute names, not custom)
- ✅ W3C trace context propagation across all 3 layers
- ✅ Separate App Insights resource for browser RUM (key is public-facing)
- ✅ Eval-trace correlation via operation_Id (Q7 of agent-monitoring.kql)
- ✅ percentile() for latency (NOT avg) — App Insights observability best practice

## Stitched-together flow

```
[Browser] click button → trackAgentInvocation() emits gen_ai.agent.invocation event
       │ traceparent: 00-<trace_id>-<browser_span_id>-01
       ▼
[FastAPI] /api/chat → reads traceparent → starts OTel span gen_ai.agent.run
       │ traceparent: 00-<trace_id>-<backend_span_id>-01
       ▼
[Foundry] /responses → executes agent → emits its own OTel spans
                                          (model_invoke, tool_invoke)
       │
       ▼
[App Insights] all 3 layers' spans share <trace_id> → KQL Q7 stitches them via operation_Id
```

## Source

- Sub-skill: https://github.com/microsoft/azure-skills/tree/main/skills/microsoft-foundry (observability sub-section)
- Browser code: `skill-demos/applicationinsights-web-ts/appInsights.ts`
- KQL queries: `skill-demos/kql/agent-monitoring.kql`
- Backend log endpoint: `Foundry-Hosted-Agent-Toolbox-Demo/app/server.py /api/agent-logs`
