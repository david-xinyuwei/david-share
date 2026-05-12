/**
 * Application Insights Browser Instrumentation for the Foundry Demo UI
 *
 * Generated using the `applicationinsights-web-ts` skill from microsoft/skills.
 *
 * What this skill enforced:
 *   1. Use `@microsoft/applicationinsights-web` (the official browser SDK).
 *   2. Connection string is plaintext at runtime (no Entra auth in browser) —
 *      use a SEPARATE App Insights resource for browser RUM.
 *   3. Enable W3C distributed tracing so browser spans correlate to backend
 *      OpenTelemetry traces (FastAPI server.py).
 *   4. Add a telemetry initializer to scrub sensitive query-string params.
 *   5. Emit GenAI agent spans following OpenTelemetry GenAI semantic conventions.
 *
 * Source: https://github.com/microsoft/skills/blob/main/.github/skills/applicationinsights-web-ts/SKILL.md
 *         (fetched 2026-05-12)
 *
 * To use this in the Foundry-Hosted-Agent-Toolbox-Demo dashboard:
 *
 *   1. npm i --save @microsoft/applicationinsights-web @microsoft/applicationinsights-clickanalytics-js
 *   2. Set VITE_APPINSIGHTS_CONNECTION_STRING in your .env
 *      (use a separate App Insights resource — its key is exposed to all clients)
 *   3. Import this module as the FIRST script in your bundle entry point.
 */
import { ApplicationInsights, ITelemetryItem } from "@microsoft/applicationinsights-web";
import { ClickAnalyticsPlugin } from "@microsoft/applicationinsights-clickanalytics-js";

const clickPlugin = new ClickAnalyticsPlugin();

export const appInsights = new ApplicationInsights({
  config: {
    connectionString: import.meta.env.VITE_APPINSIGHTS_CONNECTION_STRING,
    enableAutoRouteTracking: true,
    enableCorsCorrelation: true,
    enableRequestHeaderTracking: true,
    enableResponseHeaderTracking: true,
    distributedTracingMode: 2, // AI_AND_W3C — emit traceparent for backend OTel correlation
    autoTrackPageVisitTime: true,
    extensions: [clickPlugin],
    extensionConfig: {
      [clickPlugin.identifier]: {
        autoCapture: true,
        dataTags: { useDefaultContentNameOrId: true, customDataPrefix: "data-ai-" },
      },
    },
  },
});

appInsights.loadAppInsights();

// Telemetry initializer — enrich + scrub PII
appInsights.addTelemetryInitializer((item: ITelemetryItem) => {
  item.tags ??= {};
  item.tags["ai.cloud.role"] = "foundry-demo-ui";
  item.tags["ai.cloud.roleInstance"] = window.location.hostname;
  item.data ??= {};
  item.data["app.version"] = import.meta.env.VITE_APP_VERSION ?? "dev";

  // Drop noisy /api/health page views (polled every 3s)
  if (item.baseType === "PageviewData" && item.baseData?.uri?.endsWith("/api/health")) {
    return false;
  }

  // Scrub Bearer tokens accidentally landing in URLs (defensive)
  if (item.baseData?.uri) {
    item.baseData.uri = item.baseData.uri.replace(/([?&](token|sig|key|access_token)=)[^&]+/gi, "$1REDACTED");
  }
  return true;
});

appInsights.trackPageView();

// ============================================================================
// GenAI agent helpers — emit OpenTelemetry GenAI semantic conventions
// ============================================================================
// Each agent invocation in the demo UI calls trackAgentInvocation(), which emits
// a custom event that App Insights will surface as a GenAI agent span and that
// correlates to the backend FastAPI server's OTel spans via traceparent.

interface AgentSpanAttrs {
  agentName: string;
  agentId: string;
  modelName?: string;
  toolNames?: string[];
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  durationMs: number;
  status: "success" | "error";
  errorMessage?: string;
}

export function trackAgentInvocation(attrs: AgentSpanAttrs): void {
  appInsights.trackEvent(
    {
      name: "gen_ai.agent.invocation",
    },
    {
      // OTel GenAI semantic conventions
      "gen_ai.system": "azure_ai_foundry",
      "gen_ai.operation.name": "agent_invoke",
      "gen_ai.agent.name": attrs.agentName,
      "gen_ai.agent.id": attrs.agentId,
      "gen_ai.request.model": attrs.modelName ?? "unknown",
      "gen_ai.usage.input_tokens": attrs.inputTokens ?? 0,
      "gen_ai.usage.output_tokens": attrs.outputTokens ?? 0,
      "gen_ai.usage.total_tokens": attrs.totalTokens ?? 0,
      "agent.tools.invoked": JSON.stringify(attrs.toolNames ?? []),
      "duration_ms": attrs.durationMs,
      "status": attrs.status,
      "error.message": attrs.errorMessage ?? "",
    }
  );
}

export function trackToolCall(toolName: string, durationMs: number, success: boolean): void {
  appInsights.trackDependencyData({
    id: crypto.randomUUID(),
    name: `tool:${toolName}`,
    duration: durationMs,
    success,
    responseCode: success ? 200 : 500,
    type: "GenAI.Tool",
    target: "foundry-toolbox",
  });
}

// Hook into the existing sendChat() function in index.html:
//
//   async function sendChat() {
//     const t0 = performance.now();
//     const response = await fetch('/api/chat', {...});
//     const data = await response.json();
//     trackAgentInvocation({
//       agentName: data.agent_name,
//       agentId: data.agent_id,
//       modelName: 'gpt-4.1-mini',
//       toolNames: data.tool_calls.map(t => t.name),
//       inputTokens: data.input_tokens,
//       outputTokens: data.output_tokens,
//       totalTokens: data.total_tokens,
//       durationMs: performance.now() - t0,
//       status: response.ok ? 'success' : 'error',
//     });
//   }
