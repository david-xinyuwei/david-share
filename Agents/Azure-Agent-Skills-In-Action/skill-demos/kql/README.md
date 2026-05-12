# KQL Skill — Live Demo

> Generated using the `kql` skill from
> [microsoft/skills](https://github.com/microsoft/skills/tree/main/.github/skills/kql).

## What was produced

7 production-ready KQL queries ([`agent-monitoring.kql`](agent-monitoring.kql)) that monitor the
Foundry-Hosted-Agent-Toolbox-Demo via Application Insights. Each query follows the
discipline rules from the `kql` skill SKILL.md.

## Queries delivered

| # | Query | Purpose | Already used in our demo |
|---|-------|---------|---------------------------|
| Q1 | Last 50 hosted-agent logs | Powers `/api/agent-logs` endpoint in `app/server.py` | ✅ Yes |
| Q2 | Invocations per agent persona (24h) | Compare default / math-only / rag-only usage | New |
| Q3 | Tool usage breakdown | Which Toolbox tools get called most | New |
| Q4 | Token consumption per model | Cost analysis | New |
| Q5 | Error rate per agent per hour | Anomaly detection | New |
| Q6 | p50/p95/p99 latency per agent | Performance SLOs | New |
| Q7 | Distributed trace correlation | Browser → FastAPI full operation graph | New |

## Reproducible prompt

> ```
> Using the kql skill, write 7 KQL queries against Application Insights tables
> (AppTraces, AppEvents, AppDependencies, AppExceptions) for monitoring our
> Foundry hosted-agent-toolbox-demo.
>
> Hard requirements per the skill's discipline rules:
>   1. ALWAYS cast dynamic columns (Properties["..."]) BEFORE using them in
>      summarize-by, order-by, or join-on. Use tostring/toint/todouble.
>      Skill quote: "Any time you use a dynamic-typed column in by, on, or order by,
>      wrap it in an explicit cast."
>   2. Time ranges via ago() — NEVER hardcoded UTC strings.
>   3. project after the FINAL summarize to drop unused columns.
>   4. top/take to bound result size.
>   5. percentile() instead of avg() for latency (skill: "avg lies").
>   6. has/contains used appropriately for tokenized vs free-text search.
>   7. let bindings for query parameters (e.g., target_trace_id).
>
> The queries should reflect the agent's gen_ai.* OTel semantic conventions:
>   - Properties["gen_ai.agent.name"]
>   - Properties["gen_ai.usage.{input,output,total}_tokens"]
>   - Properties["gen_ai.request.model"]
>   - Properties["agent.tools.invoked"] (JSON array)
>   - Properties["status"] (success | error)
>   - Properties["duration_ms"]
>
> Output: skill-demos/kql/agent-monitoring.kql
> ```

## Skill rules enforced (with examples)

| Skill rule | Example from our queries |
|------------|--------------------------|
| Cast dynamic before summarize-by | Q2: `extend agent_name = tostring(Properties["gen_ai.agent.name"])` then `summarize ... by agent_name` |
| Cast dynamic before order-by | Q4: `extend total_tokens = toint(...)` then `order by sum_total desc` |
| Time range with ago() | All queries: `ago(1h)`, `ago(24h)`, `ago(7d)` |
| project at end | Q1: `project TimeGenerated, SeverityLevel, Message` |
| Bounded result size | Q1: `top 50`, others use `summarize` which is implicitly bounded |
| percentile not avg for latency | Q6: `percentile(duration_ms, 50/95/99)` not `avg(duration_ms)` |
| Filter low-volume noise | Q5: `where total >= 5` to skip 1-sample buckets that look like 100% errors |
| let bindings for params | Q7: `let target_trace = "REPLACE_WITH_OPERATION_ID";` |
| union for cross-table | Q7: `union AppTraces, AppEvents, AppDependencies, AppExceptions` |

## Why this matters

Without the skill, an agent would likely:
- Forget to cast `Properties["gen_ai.agent.name"]` → "Summarize group key is of a 'dynamic' type" error
- Use `avg()` for latency → masks the tail behavior that matters most
- Hardcode UTC strings instead of `ago()` → queries become stale within hours
- Forget to bound result size → hits Log Analytics row limit, returns truncated data
- Order by raw dynamic fields → "order operator: key can't be of dynamic type" error

With the skill: all of the above gotchas are enforced as discipline rules in SKILL.md,
so the queries work the first time.

## Source

- Skill: https://github.com/microsoft/skills/blob/main/.github/skills/kql/SKILL.md
- KQL docs: https://learn.microsoft.com/en-us/kusto/query/
- App Insights table reference: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/apptraces
