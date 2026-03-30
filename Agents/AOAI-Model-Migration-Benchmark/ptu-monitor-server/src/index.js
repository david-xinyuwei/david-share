require("./telemetry");

const express = require("express");
const axios = require("axios");
const winston = require("winston");
const { trace, metrics, SpanStatusCode } = require("@opentelemetry/api");

const app = express();
const port = Number(process.env.PORT || "8080");
const tracer = trace.getTracer("PtuMonitor.Server");
const meter = metrics.getMeter("PtuMonitor.Server");

// ── PTU Metrics (sent to App Insights as customMetrics) ──
const ptuUtilization = meter.createHistogram("ptu.utilization_pct", { unit: "percent", description: "PTU TPM utilization percentage" });
const ptuRemainingTokens = meter.createHistogram("ptu.remaining_tokens", { description: "Remaining tokens in current TPM window" });
const ptuRemainingRequests = meter.createHistogram("ptu.remaining_requests", { description: "Remaining requests in current RPM window" });
const ptuRequestCounter = meter.createCounter("ptu.requests_total", { description: "Total AOAI requests" });
const ptu429Counter = meter.createCounter("ptu.http429_count", { description: "HTTP 429 throttled requests" });
const ptuTtftHistogram = meter.createHistogram("ptu.ttft_ms", { unit: "ms", description: "Time to first token" });
const ptuE2eHistogram = meter.createHistogram("ptu.e2e_ms", { unit: "ms", description: "End-to-end latency" });
const routingDecisionCounter = meter.createCounter("ptu.routing_decision", { description: "Routing decisions: ptu vs paygo" });

const logger = winston.createLogger({
  level: "info",
  format: winston.format.combine(winston.format.timestamp(), winston.format.json()),
  defaultMeta: { service: process.env.OTEL_SERVICE_NAME || "ptu-monitor-server" },
  transports: [new winston.transports.Console()],
});

// ── Configuration ──
const PTU_ENDPOINT = process.env.PTU_ENDPOINT;
const PAYGO_ENDPOINT = process.env.PAYGO_ENDPOINT;
const PTU_API_KEY = process.env.PTU_API_KEY;
const PAYGO_API_KEY = process.env.PAYGO_API_KEY;
const DEPLOYMENT = process.env.AOAI_DEPLOYMENT || "gpt-5.4-nano";
const API_VERSION = process.env.AOAI_API_VERSION || "2025-04-01-preview";
const ROUTING_THRESHOLD = Number(process.env.ROUTING_THRESHOLD || "95");

// ── State: last known PTU utilization ──
let lastPtuUtilizationPct = 0;
let lastRemainingTokens = null;
let lastLimitTokens = null;

app.use(express.json());

// ── Health ──
app.get("/healthz", (_req, res) => {
  res.json({
    ok: true,
    service: process.env.OTEL_SERVICE_NAME || "ptu-monitor-server",
    ptuEndpoint: PTU_ENDPOINT ? "configured" : "NOT SET",
    paygoEndpoint: PAYGO_ENDPOINT ? "configured" : "NOT SET",
    deployment: DEPLOYMENT,
    routingThreshold: ROUTING_THRESHOLD,
    lastUtilization: lastPtuUtilizationPct,
  });
});

// ── Simulate: manually set utilization for testing routing logic ──
app.post("/api/simulate", (req, res) => {
  const newUtil = req.body.utilization_pct;
  if (typeof newUtil !== "number") {
    return res.status(400).json({ error: "provide utilization_pct as number" });
  }
  const oldUtil = lastPtuUtilizationPct;
  lastPtuUtilizationPct = newUtil;
  logger.info("Simulated utilization change", { from: oldUtil, to: newUtil, threshold: ROUTING_THRESHOLD });
  res.json({
    message: `Utilization set from ${oldUtil}% to ${newUtil}%`,
    routing_decision: newUtil >= ROUTING_THRESHOLD ? "SWITCH_TO_PAYGO" : "KEEP_ON_PTU",
    threshold: ROUTING_THRESHOLD,
  });
});

// ── Main: proxy AOAI request with PTU monitoring + proactive routing ──
app.post("/api/chat", async (req, res) => {
  const startedAt = Date.now();

  await tracer.startActiveSpan("ptu.proxy-request", async (span) => {
    const usePtu = lastPtuUtilizationPct < ROUTING_THRESHOLD && PTU_ENDPOINT && PTU_API_KEY;
    const targetEndpoint = usePtu ? PTU_ENDPOINT : (PAYGO_ENDPOINT || PTU_ENDPOINT);
    const targetApiKey = usePtu ? PTU_API_KEY : (PAYGO_API_KEY || PTU_API_KEY);
    const backend = usePtu ? "ptu" : "paygo";

    span.setAttribute("ptu.backend", backend);
    span.setAttribute("ptu.utilization_before", lastPtuUtilizationPct);
    span.setAttribute("ptu.deployment", DEPLOYMENT);
    routingDecisionCounter.add(1, { backend });

    const url = `${targetEndpoint}/openai/deployments/${DEPLOYMENT}/chat/completions?api-version=${API_VERSION}`;
    const headers = { "api-key": targetApiKey, "Content-Type": "application/json" };

    const aoaiPayload = {
      messages: req.body.messages || [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: "Hello" }
      ],
      max_completion_tokens: req.body.max_completion_tokens || 200,
      stream: true,
    };

    let ttft = null;
    let responseStatus = null;
    let remainingTokens = null;
    let limitTokens = null;
    let remainingRequests = null;
    let retryAfter = null;
    let outputChunks = 0;
    let fullText = "";

    try {
      const axiosResponse = await axios({
        method: "post", url, headers, data: aoaiPayload,
        responseType: "stream", timeout: 120000,
        validateStatus: () => true,
      });

      responseStatus = axiosResponse.status;

      // ── Extract rate-limit headers ──
      remainingTokens = axiosResponse.headers["x-ratelimit-remaining-tokens"];
      limitTokens = axiosResponse.headers["x-ratelimit-limit-tokens"];
      remainingRequests = axiosResponse.headers["x-ratelimit-remaining-requests"];
      retryAfter = axiosResponse.headers["retry-after-ms"];

      // ── Calculate and record utilization ──
      if (remainingTokens && limitTokens) {
        const rem = parseInt(remainingTokens);
        const lim = parseInt(limitTokens);
        const utilPct = ((lim - rem) / lim) * 100;

        ptuUtilization.record(utilPct, { backend, deployment: DEPLOYMENT });
        ptuRemainingTokens.record(rem, { backend });
        lastPtuUtilizationPct = utilPct;
        lastRemainingTokens = rem;
        lastLimitTokens = lim;

        span.setAttribute("ptu.utilization_pct", Math.round(utilPct * 100) / 100);
        span.setAttribute("ptu.remaining_tokens", rem);
        span.setAttribute("ptu.limit_tokens", lim);
      }

      if (remainingRequests) {
        ptuRemainingRequests.record(parseInt(remainingRequests), { backend });
      }

      ptuRequestCounter.add(1, { backend, status: String(responseStatus), deployment: DEPLOYMENT });

      if (responseStatus === 429) {
        ptu429Counter.add(1, { backend });
        span.setAttribute("ptu.throttled", true);
        logger.warn("HTTP 429 throttled", { backend, retryAfter, remainingTokens, limitTokens });
      }

      // ── Stream response and measure TTFT ──
      if (responseStatus === 200) {
        let buffer = "";
        await new Promise((resolve, reject) => {
          axiosResponse.data.on("data", (chunk) => {
            buffer += chunk.toString();
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";
            for (const line of lines) {
              if (line.startsWith("data: ") && line !== "data: [DONE]") {
                if (ttft === null) {
                  ttft = Date.now() - startedAt;
                  ptuTtftHistogram.record(ttft, { backend, deployment: DEPLOYMENT });
                  span.setAttribute("ptu.ttft_ms", ttft);
                }
                try {
                  const parsed = JSON.parse(line.slice(6));
                  const content = parsed.choices?.[0]?.delta?.content || "";
                  if (content) { fullText += content; outputChunks++; }
                } catch {}
              }
            }
          });
          axiosResponse.data.on("end", resolve);
          axiosResponse.data.on("error", reject);
        });
      }

      const e2eMs = Date.now() - startedAt;
      ptuE2eHistogram.record(e2eMs, { backend, deployment: DEPLOYMENT, status: String(responseStatus) });
      span.setStatus({ code: responseStatus === 200 ? SpanStatusCode.OK : SpanStatusCode.ERROR });

      logger.info("AOAI request completed", {
        backend, status: responseStatus, ttft, e2eMs, outputChunks,
        remainingTokens, limitTokens,
        utilization: lastPtuUtilizationPct.toFixed(1) + "%",
        routing: lastPtuUtilizationPct >= ROUTING_THRESHOLD ? "SWITCH_PAYGO" : "KEEP_PTU",
      });

      res.json({
        backend, status: responseStatus, ttft_ms: ttft, e2e_ms: e2eMs,
        output_chunks: outputChunks,
        output_preview: fullText.slice(0, 200),
        ratelimit: {
          remaining_tokens: remainingTokens, limit_tokens: limitTokens,
          remaining_requests: remainingRequests,
          utilization_pct: Math.round(lastPtuUtilizationPct * 100) / 100,
          retry_after_ms: retryAfter,
        },
        routing: {
          threshold: ROUTING_THRESHOLD,
          decision: lastPtuUtilizationPct >= ROUTING_THRESHOLD ? "SWITCH_TO_PAYGO" : "KEEP_ON_PTU",
        },
      });
    } catch (error) {
      const e2eMs = Date.now() - startedAt;
      ptuE2eHistogram.record(e2eMs, { backend, deployment: DEPLOYMENT, status: "error" });
      ptuRequestCounter.add(1, { backend, status: "error", deployment: DEPLOYMENT });
      span.recordException(error);
      span.setStatus({ code: SpanStatusCode.ERROR, message: error.message });
      logger.error("AOAI request failed", { backend, error: error.message });
      res.status(502).json({ backend, error: error.message, e2e_ms: e2eMs });
    } finally {
      span.end();
    }
  });
});

// ── Dashboard: current PTU status ──
app.get("/api/status", (_req, res) => {
  res.json({
    deployment: DEPLOYMENT,
    ptu_utilization_pct: Math.round(lastPtuUtilizationPct * 100) / 100,
    remaining_tokens: lastRemainingTokens, limit_tokens: lastLimitTokens,
    routing_threshold: ROUTING_THRESHOLD,
    routing_decision: lastPtuUtilizationPct >= ROUTING_THRESHOLD ? "SWITCH_TO_PAYGO" : "KEEP_ON_PTU",
    timestamp: new Date().toISOString(),
  });
});

// ── Stress test endpoint ──
app.post("/api/stress", async (req, res) => {
  const concurrency = req.body.concurrency || 10;
  const total = req.body.total || 50;
  const results = [];
  let http429Count = 0;

  await tracer.startActiveSpan("ptu.stress-test", async (span) => {
    span.setAttribute("stress.concurrency", concurrency);
    span.setAttribute("stress.total", total);
    const semaphore = { active: 0 };

    const sendOne = async (i) => {
      while (semaphore.active >= concurrency) await new Promise(r => setTimeout(r, 50));
      semaphore.active++;
      try {
        const r = await axios.post(`http://localhost:${port}/api/chat`, {
          messages: [
            { role: "system", content: "You are a helpful assistant." },
            { role: "user", content: `Stress test #${i}: What is cloud computing?` }
          ],
          max_completion_tokens: 100,
        }, { timeout: 120000 });
        results.push({ id: i, status: r.data.status, backend: r.data.backend, ttft_ms: r.data.ttft_ms, e2e_ms: r.data.e2e_ms, utilization_pct: r.data.ratelimit?.utilization_pct, routing: r.data.routing?.decision });
        if (r.data.status === 429) http429Count++;
      } catch (error) { results.push({ id: i, error: error.message }); }
      semaphore.active--;
    };

    await Promise.all(Array.from({ length: total }, (_, i) => sendOne(i)));
    span.end();
    res.json({ total, concurrency, http429_count: http429Count, results: results.sort((a, b) => a.id - b.id) });
  });
});

app.listen(port, () => {
  logger.info("PTU Monitor Server listening", { port, deployment: DEPLOYMENT, routingThreshold: ROUTING_THRESHOLD });
});
