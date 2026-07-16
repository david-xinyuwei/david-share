import { randomUUID } from "node:crypto";
import { readFile, realpath } from "node:fs/promises";
import path from "node:path";

const RETRYABLE_STATUS = new Set([424, 429, 502, 503, 504]);
const ARTIFACT_FILENAMES = new Set([
  "evidence.json",
  "meeting-analysis.json",
  "meeting-events.json",
  "meeting-follow-up.eml",
  "meeting-summary.pptx",
  "mind-map.json",
  "mind-map.mmd",
  "mind-map.png",
  "mind-map.svg",
]);

export class FoundryClientError extends Error {
  constructor(message, statusCode = 502, code = "foundry_request_failed") {
    super(message);
    this.name = "FoundryClientError";
    this.statusCode = statusCode;
    this.code = code;
  }
}

export function loadRuntimeEnvironment(environment = process.env, projectRoot) {
  void projectRoot;
  return { ...environment };
}

export function createLocalAgentClient(environment = process.env) {
  const localAgentUrl = optionalUrl(environment.MEETING_AGENT_LOCAL_AGENT_URL);
  if (!localAgentUrl) {
    throw new Error("MEETING_AGENT_LOCAL_AGENT_URL is required.");
  }
  const agentName = validateAgentName(environment.MEETING_AGENT_NAME || "meeting-agent");
  const runtimeMode = validateLocalRuntimeMode(environment.MEETING_AGENT_RUNTIME_MODE);
  const localSessionHome = environment.MEETING_AGENT_LOCAL_SESSION_HOME
    ? path.resolve(environment.MEETING_AGENT_LOCAL_SESSION_HOME)
    : null;

  return {
    mode: runtimeMode,
    agentName,

    async createSession() {
      return randomUUID();
    },

    async invoke(sessionId, payload) {
      validateSessionId(sessionId);
      const endpoint =
        `${localAgentUrl}/invocations?agent_session_id=${encodeURIComponent(sessionId)}`;
      const response = await requestWithRetry(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await parseJson(response);
      return { ...body, agent_session_id: body.agent_session_id || sessionId };
    },

    async invokeStream(sessionId, payload, signal) {
      validateSessionId(sessionId);
      const endpoint =
        `${localAgentUrl}/invocations_stream?agent_session_id=${encodeURIComponent(sessionId)}`;
      let response;
      try {
        response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: signal
            ? AbortSignal.any([signal, AbortSignal.timeout(180_000)])
            : AbortSignal.timeout(180_000),
        });
      } catch (error) {
        throw new FoundryClientError(
          `Streaming backend could not be reached: ${error instanceof Error ? error.message : "network error"}`,
          502,
          "streaming_unreachable",
        );
      }
      if (!response.ok) {
        const errorBody = await response.text();
        throw new FoundryClientError(
          `Streaming backend returned HTTP ${response.status}${safeErrorSuffix(errorBody)}.`,
          response.status,
          "streaming_request_failed",
        );
      }
      if (!response.body) {
        throw new FoundryClientError(
          "Streaming backend returned an empty response body.",
          502,
          "streaming_empty_response",
        );
      }
      return response;
    },

    async downloadFile(sessionId, artifactPath) {
      validateSessionId(sessionId);
      const safePath = validateArtifactPath(artifactPath);
      if (!localSessionHome) {
        throw new FoundryClientError(
          "MEETING_AGENT_LOCAL_SESSION_HOME is required for artifact downloads.",
          503,
          "local_session_home_missing",
        );
      }
      return readFile(await resolveExistingInside(localSessionHome, safePath));
    },
  };
}

function validateLocalRuntimeMode(value) {
  if (!value || value === "local") return "local";
  if (value === "aoai") return "aoai";
  throw new Error("MEETING_AGENT_RUNTIME_MODE must be local or aoai.");
}


async function requestWithRetry(url, options) {
  const attempts = 3;
  let response;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      response = await fetch(url, { ...options, signal: AbortSignal.timeout(90_000) });
    } catch (error) {
      if (attempt === attempts - 1) {
        throw new FoundryClientError(
          `Foundry could not be reached: ${error instanceof Error ? error.message : "network error"}`,
          502,
          "foundry_unreachable",
        );
      }
      await delay(1_000 * 2 ** attempt);
      continue;
    }
    if (response.ok) {
      return response;
    }
    if (!RETRYABLE_STATUS.has(response.status) || attempt === attempts - 1) {
      const errorBody = await response.text();
      throw new FoundryClientError(
        `Foundry returned HTTP ${response.status}${safeErrorSuffix(errorBody)}.`,
        response.status,
      );
    }
    await response.body?.cancel();
    await delay(1_000 * 2 ** attempt);
  }
  throw new FoundryClientError("Foundry request failed without a response.");
}

async function parseJson(response) {
  try {
    return await response.json();
  } catch {
    throw new FoundryClientError("Foundry returned a non-JSON response.");
  }
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function safeErrorSuffix(value) {
  if (!value) return "";
  try {
    const parsed = JSON.parse(value);
    const code = parsed.error?.code || parsed.error;
    return typeof code === "string" ? ` (${code.slice(0, 80)})` : "";
  } catch {
    return "";
  }
}

function optionalUrl(value) {
  if (!value) return null;
  const parsed = new URL(value);
  if (!new Set(["http:", "https:"]).has(parsed.protocol)) {
    throw new Error("MEETING_AGENT_LOCAL_AGENT_URL must use HTTP or HTTPS.");
  }
  return parsed.toString().replace(/\/$/, "");
}


export function validateAgentName(value) {
  if (!/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(value)) {
    throw new Error("MEETING_AGENT_NAME is invalid.");
  }
  return value;
}

export function validateSessionId(value) {
  if (!/^[A-Za-z0-9_-]{8,128}$/.test(value)) {
    throw new FoundryClientError("Agent session ID is invalid.", 400, "invalid_session_id");
  }
  return value;
}

export function validateArtifactPath(value) {
  const match =
    typeof value === "string"
      ? /^artifacts\/[A-Za-z0-9_-]{8,128}\/([A-Za-z0-9._-]+)$/.exec(value)
      : null;
  if (!match || !ARTIFACT_FILENAMES.has(match[1])) {
    throw new FoundryClientError("Artifact path is invalid.", 400, "invalid_artifact_path");
  }
  return value;
}

export function resolveInside(root, relativePath) {
  const resolved = path.resolve(root, relativePath);
  const prefix = `${path.resolve(root)}${path.sep}`;
  if (!resolved.startsWith(prefix)) {
    throw new FoundryClientError("Artifact path escapes the session directory.", 400);
  }
  return resolved;
}

export async function resolveExistingInside(root, relativePath) {
  const resolved = resolveInside(root, relativePath);
  let canonicalRoot;
  let canonicalResolved;
  try {
    [canonicalRoot, canonicalResolved] = await Promise.all([realpath(root), realpath(resolved)]);
  } catch (error) {
    if (error?.code === "ENOENT") {
      throw new FoundryClientError("Artifact file was not found.", 404, "artifact_not_found");
    }
    throw error;
  }
  const relative = path.relative(canonicalRoot, canonicalResolved);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new FoundryClientError("Artifact path escapes the session directory.", 400);
  }
  return canonicalResolved;
}