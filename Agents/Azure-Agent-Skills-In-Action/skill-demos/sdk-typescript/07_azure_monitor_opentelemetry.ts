// TRIPLE:
//   Skill: azure-monitor-opentelemetry-ts
//   Prompt: "Using azure-monitor-opentelemetry-ts skill, write TypeScript code that configures server-side OTel for Express/Fastify and emits GenAI spans."
//   Deliverable: This file
//   Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-typescript/skills/azure-monitor-opentelemetry-ts

import { useAzureMonitor, AzureMonitorOpenTelemetryOptions } from "@azure/monitor-opentelemetry";
import { trace, SpanKind, SpanStatusCode } from "@opentelemetry/api";

// Must be called BEFORE importing express/fastify
const options: AzureMonitorOpenTelemetryOptions = {
  azureMonitorExporterOptions: {
    connectionString: process.env["APPLICATIONINSIGHTS_CONNECTION_STRING"]!,
  },
  instrumentationOptions: {
    http: { enabled: true },
  },
};
useAzureMonitor(options);

const tracer = trace.getTracer("skill-demo-genai");

async function handleGenAIRequest(prompt: string): Promise<string> {
  return tracer.startActiveSpan("gen_ai.chat", { kind: SpanKind.CLIENT }, async (span) => {
    try {
      span.setAttribute("gen_ai.system", "az.ai.inference");
      span.setAttribute("gen_ai.request.model", "gpt-4o");
      span.setAttribute("gen_ai.request.max_tokens", 1024);
      span.setAttribute("gen_ai.request.temperature", 0.7);

      // Simulate LLM call
      const response = `Response to: ${prompt}`;

      span.setAttribute("gen_ai.response.finish_reasons", ["stop"]);
      span.setAttribute("gen_ai.usage.input_tokens", prompt.split(" ").length);
      span.setAttribute("gen_ai.usage.output_tokens", response.split(" ").length);
      span.setStatus({ code: SpanStatusCode.OK });
      return response;
    } catch (err: any) {
      span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
      throw err;
    } finally {
      span.end();
    }
  });
}

// Demo
(async () => {
  const result = await handleGenAIRequest("What is Azure Monitor OpenTelemetry?");
  console.log(`GenAI result: ${result}`);
  console.log("Traces exported to Application Insights.");
})();
