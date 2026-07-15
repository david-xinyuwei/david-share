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

export function meetingRecordEvents(value: string): MeetingEvent[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error("Meeting JSON is not valid JSON.");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Meeting JSON must be an object.");
  }
  const record = parsed as Record<string, unknown>;
  const meeting = record.meeting as Record<string, unknown> | undefined;
  const transcript = record.transcript;
  if (!meeting || typeof meeting.id !== "string" || !meeting.id.trim()) {
    throw new Error("Meeting JSON requires meeting.id.");
  }
  if (!Array.isArray(transcript) || transcript.length === 0) {
    throw new Error("Meeting JSON requires at least one transcript item.");
  }
  const sessionId = meeting.id.trim();
  const started =
    typeof meeting.started_at === "string" && Number.isFinite(Date.parse(meeting.started_at))
      ? Date.parse(meeting.started_at)
      : Date.now();
  const participants = Array.isArray(meeting.participants)
    ? meeting.participants
        .map((participant) => {
          if (!participant || typeof participant !== "object") return null;
          const value = participant as Record<string, unknown>;
          return typeof value.name === "string"
            ? [value.name, typeof value.role === "string" ? value.role : null]
                .filter(Boolean)
                .join(" — ")
            : null;
        })
        .filter(Boolean)
    : [];
  const context = [
    typeof meeting.title === "string" ? `Meeting: ${meeting.title}` : null,
    typeof meeting.objective === "string" ? `Objective: ${meeting.objective}` : null,
    participants.length ? `Participants: ${participants.join("; ")}` : null,
  ]
    .filter(Boolean)
    .join(". ");
  const events: MeetingEvent[] = [];
  if (context) {
    events.push({
      event_id: `${sessionId}-context`,
      session_id: sessionId,
      sequence: 1,
      timestamp: new Date(started).toISOString(),
      kind: "visual.frame",
      text: context,
      metadata: { source: "meeting-record-json" },
    });
  }
  for (const [index, item] of transcript.entries()) {
    if (!item || typeof item !== "object") {
      throw new Error(`Meeting transcript item ${index + 1} must be an object.`);
    }
    const entry = item as Record<string, unknown>;
    if (typeof entry.text !== "string" || !entry.text.trim()) {
      throw new Error(`Meeting transcript item ${index + 1} requires text.`);
    }
    const speaker = typeof entry.speaker === "string" ? entry.speaker.trim() : "Speaker";
    events.push({
      event_id: `${sessionId}-transcript-${index + 1}`,
      session_id: sessionId,
      sequence: events.length + 1,
      timestamp: new Date(started + events.length * 1_000).toISOString(),
      kind: "transcript.final",
      text: `[${speaker}] ${entry.text.trim()}`,
      metadata: { source: "meeting-record-json", speaker, time: entry.time ?? null },
    });
  }
  if (Array.isArray(record.visual_context)) {
    for (const [index, item] of record.visual_context.entries()) {
      if (!item || typeof item !== "object") continue;
      const visual = item as Record<string, unknown>;
      if (typeof visual.description !== "string" || !visual.description.trim()) continue;
      events.push({
        event_id: `${sessionId}-visual-${index + 1}`,
        session_id: sessionId,
        sequence: events.length + 1,
        timestamp: new Date(started + events.length * 1_000).toISOString(),
        kind: "visual.frame",
        text: visual.description.trim(),
        metadata: { source: "meeting-record-json" },
      });
    }
  }
  events.push({
    event_id: `${sessionId}-end`,
    session_id: sessionId,
    sequence: events.length + 1,
    timestamp: new Date(started + events.length * 1_000).toISOString(),
    kind: "meeting.end",
    metadata: { source: "meeting-record-json" },
  });
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