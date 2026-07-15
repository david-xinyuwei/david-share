import { AzureCliCredential } from "@azure/identity";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFile, realpath } from "node:fs/promises";
import path from "node:path";

const API_VERSION = "v1";
const FEATURE_HEADER = "HostedAgents=V1Preview";
const TOKEN_SCOPE = "https://ai.azure.com/.default";
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

export function loadAzdDeploymentEnvironment(environment = process.env, projectRoot) {
  if (environment.MEETING_AGENT_LOCAL_AGENT_URL || environment.FOUNDRY_PROJECT_ENDPOINT) {
    return { ...environment };
  }
  let values;
  try {
    values = parseAzdValues(
      execFileSync("azd", ["env", "get-values", "--no-prompt"], {
        cwd: projectRoot,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
        timeout: 10_000,
      }),
    );
  } catch {
    return { ...environment };
  }
  return {
    ...environment,
    AZURE_SUBSCRIPTION_ID: values.AZURE_SUBSCRIPTION_ID || environment.AZURE_SUBSCRIPTION_ID,
    AZURE_TENANT_ID: values.AZURE_TENANT_ID || environment.AZURE_TENANT_ID,
    FOUNDRY_PROJECT_ENDPOINT:
      values.FOUNDRY_PROJECT_ENDPOINT ||
      values.AZURE_AI_PROJECT_ENDPOINT ||
      values.AZURE_AIPROJECT_ENDPOINT,
    MEETING_AGENT_NAME: values.AGENT_MEETING_AGENT_NAME || environment.MEETING_AGENT_NAME,
  };
}

export function parseAzdValues(output) {
  const values = {};
  for (const line of output.split(/\r?\n/)) {
    const match = /^([A-Z][A-Z0-9_]*)=(.*)$/.exec(line.trim());
    if (!match) continue;
    const [, key, rawValue] = match;
    try {
      values[key] = JSON.parse(rawValue);
    } catch {
      values[key] = rawValue.replace(/^['"]|['"]$/g, "");
    }
  }
  return values;
}

export function createFoundryClient(environment = process.env) {
  const localAgentUrl = optionalUrl(environment.MEETING_AGENT_LOCAL_AGENT_URL);
  const projectEndpoint = localAgentUrl
    ? null
    : requiredProjectEndpoint(environment.FOUNDRY_PROJECT_ENDPOINT);
  const agentName = validateAgentName(environment.MEETING_AGENT_NAME || "meeting-agent");
  const runtimeMode = localAgentUrl
    ? validateLocalRuntimeMode(environment.MEETING_AGENT_RUNTIME_MODE)
    : "foundry";
  const localSessionHome = environment.MEETING_AGENT_LOCAL_SESSION_HOME
    ? path.resolve(environment.MEETING_AGENT_LOCAL_SESSION_HOME)
    : null;
  const credential = localAgentUrl
    ? null
    : new AzureCliCredential(buildAzureCliCredentialOptions(environment));

  return {
    mode: runtimeMode,
    agentName,

    async createSession() {
      if (localAgentUrl) {
        return randomUUID();
      }
      const response = await foundryFetch(
        credential,
        `${projectEndpoint}/agents/${encodeURIComponent(agentName)}/endpoint/sessions?api-version=${API_VERSION}`,
        { method: "POST", body: "{}" },
      );
      const body = await parseJson(response);
      const sessionId = body.agent_session_id;
      if (typeof sessionId !== "string" || !sessionId) {
        throw new FoundryClientError("Foundry did not return an agent session ID.");
      }
      return sessionId;
    },

    async invoke(sessionId, payload) {
      validateSessionId(sessionId);
      const endpoint = localAgentUrl
        ? `${localAgentUrl}/invocations?agent_session_id=${encodeURIComponent(sessionId)}`
        : `${projectEndpoint}/agents/${encodeURIComponent(agentName)}/endpoint/protocols/invocations?api-version=${API_VERSION}&agent_session_id=${encodeURIComponent(sessionId)}`;
      const response = localAgentUrl
        ? await requestWithRetry(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          })
        : await foundryFetch(credential, endpoint, {
            method: "POST",
            body: JSON.stringify(payload),
          });
      const body = await parseJson(response);
      return { ...body, agent_session_id: body.agent_session_id || sessionId };
    },

    async downloadFile(sessionId, artifactPath) {
      validateSessionId(sessionId);
      const safePath = validateArtifactPath(artifactPath);
      if (localAgentUrl) {
        if (!localSessionHome) {
          throw new FoundryClientError(
            "MEETING_AGENT_LOCAL_SESSION_HOME is required for local artifact downloads.",
            503,
            "local_session_home_missing",
          );
        }
        return readFile(await resolveExistingInside(localSessionHome, safePath));
      }
      const url =
        `${projectEndpoint}/agents/${encodeURIComponent(agentName)}/endpoint/sessions/` +
        `${encodeURIComponent(sessionId)}/files/content?api-version=${API_VERSION}&path=${encodeURIComponent(safePath)}`;
      const response = await foundryFetch(credential, url, { method: "GET" });
      return Buffer.from(await response.arrayBuffer());
    },
  };
}

export function buildAzureCliCredentialOptions(environment) {
  requiredGuid(environment.AZURE_TENANT_ID, "AZURE_TENANT_ID");
  return {
    subscription: requiredGuid(environment.AZURE_SUBSCRIPTION_ID, "AZURE_SUBSCRIPTION_ID"),
  };
}

function validateLocalRuntimeMode(value) {
  if (!value || value === "local") return "local";
  if (value === "aoai") return "aoai";
  throw new Error("MEETING_AGENT_RUNTIME_MODE must be local or aoai.");
}

export function validateRuntimeMode(value, localAgentUrl) {
  if (!localAgentUrl) return "foundry";
  return validateLocalRuntimeMode(value);
}

async function foundryFetch(credential, url, options) {
  const token = await credential.getToken(TOKEN_SCOPE);
  if (!token?.token) {
    throw new FoundryClientError(
      "No Microsoft Entra token is available for Foundry.",
      401,
      "entra_token_unavailable",
    );
  }
  return requestWithRetry(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${token.token}`,
      "Content-Type": "application/json",
      "Foundry-Features": FEATURE_HEADER,
      ...options.headers,
    },
  });
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

function requiredProjectEndpoint(value) {
  if (!value) {
    throw new Error("FOUNDRY_PROJECT_ENDPOINT is required when local agent mode is disabled.");
  }
  const parsed = new URL(value);
  if (parsed.protocol !== "https:" || !parsed.pathname.includes("/api/projects/")) {
    throw new Error("FOUNDRY_PROJECT_ENDPOINT must be an HTTPS Foundry project endpoint.");
  }
  return parsed.toString().replace(/\/$/, "");
}

function requiredGuid(value, name) {
  if (typeof value !== "string" || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value)) {
    throw new Error(`${name} must be a GUID in Foundry mode.`);
  }
  return value;
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