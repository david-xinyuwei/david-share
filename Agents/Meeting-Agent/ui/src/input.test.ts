import { describe, expect, it } from "vitest";

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

  it("rejects malformed provider JSONL without a silent fallback", () => {
    expect(() => jsonlEvents('{"event_id":"ok"}\nnot-json')).toThrow(
      "Provider JSONL line 2 is not valid JSON",
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
        transcript: [{ speaker: "Alex", time: "09:01", text: "We approved AOAI." }],
        visual_context: [{ description: "The diagram shows the local UI path." }],
      }),
    );
    expect(events.map((event) => event.kind)).toEqual([
      "visual.frame",
      "transcript.final",
      "visual.frame",
      "meeting.end",
    ]);
    expect(events[1].text).toBe("[Alex] We approved AOAI.");
    expect(events[0].text).toContain("Choose the demo path");
  });
});