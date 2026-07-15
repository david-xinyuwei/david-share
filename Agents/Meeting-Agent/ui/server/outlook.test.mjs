import { describe, expect, it } from "vitest";

import { openOutlookDraft, validateDraftContent } from "./outlook.mjs";

describe("New Outlook handoff", () => {
  const validDraft = Buffer.from(
    "Subject: Meeting\r\n" +
      "X-Unsent: 1\r\n" +
      "Content-Type: multipart/mixed; boundary=test\r\n\r\n" +
      "--test\r\nContent-Disposition: attachment; filename=mind-map.png\r\n\r\nA\r\n" +
      "--test\r\nContent-Disposition: attachment; filename=meeting-summary.pptx\r\n\r\nB\r\n",
  );

  it("requires X-Unsent and both generated attachments", () => {
    expect(() => validateDraftContent(validDraft)).not.toThrow();
    expect(() => validateDraftContent(Buffer.from("Subject: Meeting\r\n\r\nBody"))).toThrow(
      "not marked X-Unsent",
    );
    expect(() =>
      validateDraftContent(Buffer.from("Subject: Meeting\r\nX-Unsent: 1\r\n\r\nBody")),
    ).toThrow("must contain the mind map and PowerPoint");
  });

  it.skipIf(process.platform === "win32")("fails closed outside Windows", async () => {
    await expect(openOutlookDraft(validDraft, "draft.eml")).rejects.toThrow(
      "available only on Windows",
    );
  });
});