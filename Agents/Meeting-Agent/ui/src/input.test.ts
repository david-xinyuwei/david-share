import { describe, expect, it } from "vitest";

import { jsonlEvents, recipients, transcriptEvents } from "./input";

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
});