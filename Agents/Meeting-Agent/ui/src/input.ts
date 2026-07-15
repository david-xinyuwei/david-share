import type { MeetingEvent } from "./types";

export function transcriptEvents(
  transcript: string,
  sessionId: string = crypto.randomUUID(),
): MeetingEvent[] {
  const segments = transcript
    .split(/\r?\n/)
    .map((value) => value.trim())
    .filter(Boolean);
  if (segments.length === 0) {
    throw new Error("Meeting transcript is required.");
  }
  const started = Date.now();
  const events: MeetingEvent[] = segments.map((text, index) => ({
    event_id: `${sessionId}-transcript-${index + 1}`,
    session_id: sessionId,
    sequence: index + 1,
    timestamp: new Date(started + index * 1_000).toISOString(),
    kind: "transcript.final",
    text,
    metadata: { source: "meeting-agent-ui" },
  }));
  events.push({
    event_id: `${sessionId}-end`,
    session_id: sessionId,
    sequence: events.length + 1,
    timestamp: new Date(started + events.length * 1_000).toISOString(),
    kind: "meeting.end",
    metadata: { source: "meeting-agent-ui" },
  });
  return events;
}

export function jsonlEvents(value: string): MeetingEvent[] {
  const events = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      try {
        return JSON.parse(line) as MeetingEvent;
      } catch {
        throw new Error(`Provider JSONL line ${index + 1} is not valid JSON.`);
      }
    });
  if (events.length === 0) {
    throw new Error("Provider JSONL events are required.");
  }
  return events;
}

export function recipients(value: string): string[] {
  const items = value
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (items.length > 50) {
    throw new Error("A maximum of 50 recipients is supported.");
  }
  return items;
}