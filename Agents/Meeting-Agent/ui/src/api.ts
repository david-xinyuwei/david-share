import type {
  ApiError,
  HostedArtifact,
  MeetingEvent,
  MeetingRun,
  RunStreamEvent,
  UiConfig,
} from "./types";

export async function getConfig(): Promise<UiConfig> {
  return requestJson<UiConfig>("/api/config");
}

export async function createRun(events: MeetingEvent[], recipients: string[]): Promise<MeetingRun> {
  return requestJson<MeetingRun>("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ schema_version: 1, operation: "build", events, recipients }),
  });
}

export async function createRunStream(
  events: MeetingEvent[],
  recipients: string[],
  onEvent: (event: RunStreamEvent) => void,
  signal?: AbortSignal,
): Promise<MeetingRun> {
  const timeout = AbortSignal.timeout(180_000);
  const response = await fetch("/api/runs/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
    body: JSON.stringify({ schema_version: 1, operation: "build", events, recipients }),
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiError | null;
    throw new Error(body?.message || `Streaming request failed with HTTP ${response.status}.`);
  }
  if (!response.body) throw new Error("The streaming response body is empty.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed: MeetingRun | null = null;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() || "";
      for (const line of lines) {
        const event = parseNdjsonLine(line);
        if (!event) continue;
        onEvent(event);
        if (event.type === "error") throw new Error(event.data.message);
        if (event.type === "complete") completed = event.data.run;
      }
      if (done) break;
    }
    if (buffer.trim()) {
      const event = parseNdjsonLine(buffer);
      if (event) {
        onEvent(event);
        if (event.type === "error") throw new Error(event.data.message);
        if (event.type === "complete") completed = event.data.run;
      }
    }
  } finally {
    reader.releaseLock();
  }
  if (!completed) throw new Error("The streaming connection ended before completion.");
  return completed;
}

export function artifactUrl(run: MeetingRun, name: string): string | null {
  const artifact = run.artifacts[name];
  if (!artifact) return null;
  return artifactUrlFor(run.agent_session_id, artifact);
}

export function artifactUrlFor(
  sessionId: string,
  artifact: HostedArtifact,
): string {
  const query = new URLSearchParams({
    session_id: sessionId,
    path: artifact.path,
  });
  return `/api/files?${query.toString()}`;
}

export async function openOutlook(run: MeetingRun): Promise<void> {
  const artifact = run.artifacts.eml;
  if (!artifact) throw new Error("The agent did not produce an EML draft.");
  await requestJson("/api/outlook/open", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: run.agent_session_id, path: artifact.path }),
  });
}

async function requestJson<T = unknown>(url: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { ...options, signal: AbortSignal.timeout(100_000) });
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : "The service could not be reached.");
  }
  const body = (await response.json().catch(() => null)) as T | ApiError | null;
  if (!response.ok) {
    const apiError = body as ApiError | null;
    throw new Error(apiError?.message || `Request failed with HTTP ${response.status}.`);
  }
  if (body === null) throw new Error("The service returned an empty response.");
  return body as T;
}

function parseNdjsonLine(line: string): RunStreamEvent | null {
  if (!line.trim()) return null;
  return JSON.parse(line) as RunStreamEvent;
}