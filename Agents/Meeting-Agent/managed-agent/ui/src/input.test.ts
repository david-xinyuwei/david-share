import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

import { jsonlEvents, meetingRecordEvents, recipients, transcriptEvents } from "./input";

describe("meeting input adapters", () => {
  it("turns each transcript line into distinct finalized evidence", () => {
    const events = transcriptEvents("Alpha decision.\nBeta action.", "session-1234");
    expect(events.map((event) => event.kind)).toEqual([
      "transcript.final",
      "transcript.final",
      "meeting.end",
    ]);
    expect(events[0].text).toBe("Alpha decision.");
    expect(events[1].text).toBe("Beta action.");
  });

  it("rejects malformed ASR JSONL without a silent fallback", () => {
    expect(() => jsonlEvents('{"event_id":"ok"}\nnot-json')).toThrow(
      "ASR JSONL line 2 is not valid JSON",
    );
  });

  it("normalizes user-confirmed recipients", () => {
    expect(recipients("one@example.com; two@example.com")).toEqual([
      "one@example.com",
      "two@example.com",
    ]);
  });

  it("converts a structured meeting record into grounded events", () => {
    const events = meetingRecordEvents(
      JSON.stringify({
        meeting: {
          id: "workshop-1",
          title: "Workshop",
          objective: "Choose the demo path",
          participants: [{ name: "Alex", role: "Owner" }],
        },
        transcript: [{ speaker: "Alex", time: "09:01", text: "We approved the pilot." }],
        visual_context: [{ description: "The diagram shows the local UI path." }],
      }),
    );
    expect(events.map((event) => event.kind)).toEqual([
      "visual.frame",
      "transcript.final",
      "visual.frame",
      "meeting.end",
    ]);
    expect(events[1].text).toBe("[Alex] We approved the pilot.");
    expect(events[0].text).toContain("Choose the demo path");
  });

  it("preserves every turn and speaker in the complex Stargate fixture", () => {
    const fixture = readFileSync(
      new URL("../../examples/meeting-record-stargate.json", import.meta.url),
      "utf8",
    );
    const events = meetingRecordEvents(fixture);
    const transcriptEvents = events.filter((event) => event.kind === "transcript.final");
    const visualEvents = events.filter((event) => event.kind === "visual.frame");
    const speakers = new Set(transcriptEvents.map((event) => event.metadata.speaker));

    expect(events).toHaveLength(56);
    expect(transcriptEvents).toHaveLength(48);
    expect(visualEvents).toHaveLength(7);
    expect(speakers).toEqual(
      new Set(["Maya Chen", "Eric Zhou", "Nina Wang", "Daniel Xu"]),
    );
    expect(events[0].text).toContain("Planned duration: 95 minutes");
    expect(events[0].text).toContain("Mandarin-English code switching");
    expect(events[0].text).toContain("Hybrid conference room");
    expect(transcriptEvents[0].text).toContain("[Maya Chen]");
    expect(transcriptEvents.at(-1)?.text).toContain("July 29");
    expect(events.at(-1)?.kind).toBe("meeting.end");
  });
});