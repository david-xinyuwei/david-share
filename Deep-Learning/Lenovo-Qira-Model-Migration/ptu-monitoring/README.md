# PTU Monitoring: Azure Monitor + APIM Proactive Routing

Complete monitoring and traffic management solution for Azure OpenAI PTU deployments.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Azure Monitor                      │
│                                                      │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ PTU Metrics   │  │ Alerts   │  │ Log Analytics │  │
│  │ Utilization % │  │ 80%/95%  │  │ KQL Queries   │  │
│  │ Token Count   │  │ 429      │  │ Dashboards    │  │
│  └──────┬───────┘  └────┬─────┘  └───────┬───────┘  │
│         │               │                │           │
│         └───────────────┼────────────────┘           │
│                         │                            │
└─────────────────────────┼────────────────────────────┘
                          │ Diagnostic Settings
                          │
┌─────────────────────────┼────────────────────────────┐
│                    A P I M                            │
│                         │                            │
│   Request ──► Read cached utilization                │
│                    │                                 │
│              ┌─────┴─────┐                           │
│              │  > 95% ?  │                           │
│              └─────┬─────┘                           │
│            Yes ┌───┴───┐ No                          │
│                ▼       ▼                             │
│           ┌────────┐ ┌──────┐                        │
│           │ PAYGO  │ │ PTU  │                        │
│           └───┬────┘ └──┬───┘                        │
│               │         │                            │
│               ▼         ▼                            │
│         Response + extract x-ratelimit headers       │
│         Calculate utilization → cache (60s)          │
│         emit-metric → Application Insights           │
│                                                      │
│   On 429: cache util=100%, retry → PAYGO (safety)    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

## What's Included

| File | Purpose |
|------|---------|
| `infra/ptu-monitoring.bicep` | Deploys: Log Analytics + Diagnostic Settings + 3 Alert Rules + APIM + Backends |
| `apim-policy-ptu-routing.xml` | APIM policy: proactive PTU→PAYGO routing + 429 retry + emit-metric |
| `kql-queries.kql` | 7 KQL queries for dashboards (utilization, latency, 429s, cost, heatmap) |
| `deploy.sh` | One-command deployment script |

## Three Alert Rules

| Alert | Threshold | Severity | Action |
|-------|:---------:|:--------:|--------|
| **PTU Warning** | Utilization > 80% for 5 min | Warning (2) | Email notification |
| **PTU Critical** | Utilization > 95% for 1 min | Critical (0) | Email notification |
| **HTTP 429** | Any 429 response | Error (1) | Email notification |

## Quick Start

### Option A: Azure Monitor Only (no APIM, no code)

If you only need monitoring + alerting (no proactive routing):

```bash
# 1. Enable Diagnostic Settings (Portal)
#    AOAI resource → Monitoring → Diagnostic settings → Add
#    → AllMetrics ✓ → allLogs ✓ → Send to Log Analytics workspace

# 2. View PTU Utilization (Portal)
#    AOAI resource → Monitoring → Metrics
#    → Metric: Provisioned-managed Utilization V2

# 3. Create Alert Rules (Portal)
#    AOAI resource → Monitoring → Alerts → New alert rule
#    → Condition: ProvisionedManagedUtilizationV2 > 80
#    → Action group: email

# 4. Run KQL queries in Log Analytics
#    Copy queries from kql-queries.kql
```

### Option B: Full Deployment (Azure Monitor + APIM)

```bash
# Deploy everything with one command
chmod +x deploy.sh
./deploy.sh \
  --resource-group rg-lenovo-qira \
  --aoai-name your-aoai-resource \
  --ptu-endpoint https://your-ptu.openai.azure.com \
  --paygo-endpoint https://your-paygo.openai.azure.com \
  --email ops-team@company.com

# Then apply APIM policy:
# Portal → APIM → APIs → your API → Policy editor
# Paste contents of apim-policy-ptu-routing.xml
```

## KQL Dashboard Queries

7 queries included in `kql-queries.kql`:

| # | Query | Visualization |
|:-:|-------|:---:|
| 1 | PTU Utilization trend (5-min bins) | timechart |
| 2 | Request volume by status code | timechart |
| 3 | Token consumption over time | timechart |
| 4 | Latency distribution (P50/P95/P99) | timechart |
| 5 | 429 throttling events (detail) | table |
| 6 | Utilization heatmap (hour × day) | columnchart |
| 7 | Daily cost estimation (USD) | barchart |

## APIM Policy Features

The `apim-policy-ptu-routing.xml` policy implements:

1. **Read cached utilization** from previous response
2. **Route decision**: utilization > threshold → PAYGO, else → PTU
3. **Extract headers**: `x-ratelimit-remaining-tokens` / `limit-tokens` from response
4. **Calculate utilization** and cache for 60s
5. **emit-metric** to Application Insights for custom dashboards
6. **429 safety net**: on HTTP 429, cache `util=100%`, retry on PAYGO

### APIM Setup Steps

1. Create two Named Values: `ptu-routing-threshold` = `95`, `ptu-deployment` = model name
2. Create two Backends: `ptu-backend` (PTU URL) and `paygo-backend` (PAYGO URL)
3. Apply policy XML to your API's operations

## Validation

After deployment, verify with the stress test tool:

```bash
python ../scripts/stress_test_tpm_utilization.py \
  --endpoint https://YOUR_PTU.openai.azure.com \
  --api-key YOUR_KEY \
  --deployment gpt-5.4-nano \
  --concurrency 50 --total 300 \
  --output stress-results.json
```

Check:
- [ ] Diagnostic Settings active (Portal → AOAI → Monitoring → Diagnostic settings)
- [ ] Alert rules visible (Portal → Monitor → Alerts → Alert rules)
- [ ] KQL queries return data (after ~5 min of traffic)
- [ ] APIM routing works (check `X-Routing-Decision` response header)

## Related

- **Section 7** in the main README covers the full rationale and comparison
- `../ptu-monitor-server/` — Node.js proxy PoC with App Insights integration
- `../scripts/stress_test_tpm_utilization.py` — Python stress test for header validation
