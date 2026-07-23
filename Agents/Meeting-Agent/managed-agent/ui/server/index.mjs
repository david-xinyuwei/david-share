import express from "express";
import { once } from "node:events";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";

import {
  createLocalAgentClient,
  FoundryClientError,
  loadRuntimeEnvironment,
} from "./foundry-client.mjs";
import { openOutlookDraft, OutlookHandoffError } from "./outlook.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const distribution = path.resolve(here, "../dist");
const projectRoot = path.resolve(here, "../..");
const port = Number.parseInt(process.env.PORT || "4173", 10);
const host = "127.0.0.1";
const localAgent = createLocalAgentClient(loadRuntimeEnvironment(process.env, projectRoot));
const runtimeAttestation = validateRuntimeAttestation(
  process.env.MEETING_AGENT_RUNTIME_ATTESTATION,
);
const app = express();

const runSchema = z.object({
  schema_version: z.literal(1).default(1),
  operation: z.literal("build").default("build"),
  events: z.array(z.record(z.string(), z.unknown())).min(1).max(5_000),
  recipients: z.array(z.string().trim().email()).max(50).default([]),
});

const fileSchema = z.object({
  session_id: z.string().min(8).max(128),
  path: z.string().min(1).max(512),
});

app.disable("x-powered-by");
app.use((request, response, next) => {
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader("Referrer-Policy", "no-referrer");
  response.setHeader("Cross-Origin-Resource-Policy", "same-origin");
  if (request.path.startsWith("/api/")) response.setHeader("Cache-Control", "no-store");
  next();
});
app.use(express.json({ limit: "2mb", strict: true }));

app.get("/api/health", async (_request, response) => {
  try {
    const backend = await fetch(`${process.env.MEETING_AGENT_LOCAL_AGENT_URL}/readiness`, {
      signal: AbortSignal.timeout(2_000),
    });
    if (!backend.ok) throw new Error(`HTTP ${backend.status}`);
    response.json({ status: "ok", mode: localAgent.mode, agent: localAgent.agentName });
  } catch {
    response.status(503).json({
      error: "backend_unavailable",
      message: "The local artifact backend is unavailable.",
    });
  }
});

app.get("/api/config", (_request, response) => {
  response.json({
    mode: localAgent.mode,
    agent_name: localAgent.agentName,
    agent_version: process.env.MANAGED_AGENT_VERSION || null,
    model_name: process.env.MANAGED_AGENT_MODEL || null,
    reasoning_effort: null,
    authentication: "entra",
    runtime_attestation: runtimeAttestation,
    outlook_available: process.platform === "win32",
    automatic_send: false,
  });
});

app.post("/api/runs", async (request, response) => {
  try {
    const payload = runSchema.parse(request.body);
    const sessionId = await localAgent.createSession();
    const result = await localAgent.invoke(sessionId, payload);
    response.json(result);
  } catch (error) {
    sendError(response, error);
  }
});

app.post("/api/runs/stream", async (request, response) => {
  try {
    const payload = runSchema.parse(request.body);
    const sessionId = await localAgent.createSession();
    const controller = new AbortController();
    response.on("close", () => {
      if (!response.writableEnded) controller.abort();
    });
    const upstream = await localAgent.invokeStream(sessionId, payload, controller.signal);
    response.status(200);
    response.setHeader("Content-Type", "application/x-ndjson; charset=utf-8");
    response.setHeader("Cache-Control", "no-store");
    response.setHeader("Connection", "close");
    response.setHeader("X-Accel-Buffering", "no");
    response.flushHeaders();
    for await (const chunk of upstream.body) {
      if (!response.write(chunk)) await once(response, "drain");
    }
    response.end();
  } catch (error) {
    if (!response.headersSent) {
      sendError(response, error);
      return;
    }
    console.error("Streaming UI service error", error);
    response.write(`${JSON.stringify({
      type: "error",
      data: {
        error: "stream_proxy_failed",
        message: "The streaming connection ended unexpectedly.",
      },
    })}\n`);
    response.end();
  }
});

app.get("/api/files", async (request, response) => {
  try {
    const query = fileSchema.parse(request.query);
    const content = await localAgent.downloadFile(query.session_id, query.path);
    response.type(mediaType(query.path));
    response.setHeader("Content-Disposition", `inline; filename="${path.basename(query.path)}"`);
    response.send(content);
  } catch (error) {
    sendError(response, error);
  }
});

app.post("/api/outlook/open", async (request, response) => {
  try {
    const input = fileSchema.parse(request.body);
    if (!input.path.toLowerCase().endsWith(".eml")) {
      throw new OutlookHandoffError("Only an EML draft can be opened in New Outlook.", 400);
    }
    const content = await localAgent.downloadFile(input.session_id, input.path);
    response.json(await openOutlookDraft(content, input.path));
  } catch (error) {
    sendError(response, error);
  }
});

app.all("/api/{*splat}", (_request, response) => {
  response.status(404).json({ error: "not_found", message: "API route was not found." });
});

app.use(express.static(distribution, { index: false, maxAge: "1h" }));
app.get("/{*splat}", (_request, response) => {
  response.setHeader("Cache-Control", "no-store");
  response.sendFile(path.join(distribution, "index.html"));
});

app.use((error, _request, response, _next) => {
  sendError(response, error);
});

app.listen(port, host, () => {
  console.log(`Meeting Agent UI listening at http://${host}:${port} (${localAgent.mode})`);
});

function sendError(response, error) {
  if (error instanceof z.ZodError) {
    response.status(400).json({
      error: "invalid_request",
      message: "The request is invalid.",
      details: error.issues.map((issue) => ({ path: issue.path.join("."), message: issue.message })),
    });
    return;
  }
  if (error instanceof FoundryClientError || error instanceof OutlookHandoffError) {
    response.status(error.statusCode).json({ error: error.code, message: error.message });
    return;
  }
  console.error("Unhandled UI service error", error);
  response.status(500).json({ error: "internal_error", message: "The request failed unexpectedly." });
}

function mediaType(value) {
  const extension = path.extname(value).toLowerCase();
  return (
    {
      ".eml": "message/rfc822",
      ".json": "application/json",
      ".mmd": "text/plain; charset=utf-8",
      ".png": "image/png",
      ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      ".svg": "image/svg+xml",
    }[extension] || "application/octet-stream"
  );
}

function validateRuntimeAttestation(value) {
  if (value === "live-managed" || value === "test-fixture") return value;
  throw new Error(
    "MEETING_AGENT_RUNTIME_ATTESTATION must be live-managed or test-fixture.",
  );
}