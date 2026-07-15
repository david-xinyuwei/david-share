import type { ApiError, MeetingEvent, MeetingRun, UiConfig } from "./types";

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

export function artifactUrl(run: MeetingRun, name: string): string | null {
  const artifact = run.artifacts[name];
  if (!artifact) return null;
  const query = new URLSearchParams({
    session_id: run.agent_session_id,
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