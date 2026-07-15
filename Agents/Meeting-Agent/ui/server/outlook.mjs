import { mkdir, rename, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";

export class OutlookHandoffError extends Error {
  constructor(message, statusCode = 409) {
    super(message);
    this.name = "OutlookHandoffError";
    this.statusCode = statusCode;
    this.code = "outlook_handoff_unavailable";
  }
}

export async function openOutlookDraft(content, artifactPath) {
  if (process.platform !== "win32") {
    throw new OutlookHandoffError("New Outlook draft opening is available only on Windows.");
  }
  if (!Buffer.isBuffer(content) || content.length === 0) {
    throw new OutlookHandoffError("The EML artifact is empty.", 422);
  }
  validateDraftContent(content);
  const filename = path.basename(artifactPath);
  if (!/^[A-Za-z0-9._-]+\.eml$/i.test(filename)) {
    throw new OutlookHandoffError("The selected artifact is not an EML draft.", 400);
  }

  const digest = createHash("sha256").update(content).digest("hex").slice(0, 20);
  const outputDir = path.join(os.tmpdir(), "meeting-agent", digest);
  const finalPath = path.join(outputDir, filename);
  const temporaryPath = path.join(outputDir, `.${filename}.${randomUUID()}.tmp`);
  await mkdir(outputDir, { recursive: true });
  await writeFile(temporaryPath, content, { flag: "wx" });
  await rename(temporaryPath, finalPath);

  await new Promise((resolve, reject) => {
    const child = spawn("olk.exe", [finalPath], {
      detached: true,
      shell: false,
      stdio: "ignore",
      windowsHide: true,
    });
    child.once("spawn", () => {
      child.unref();
      resolve();
    });
    child.once("error", (error) => {
      reject(
        new OutlookHandoffError(
          `New Outlook could not be opened: ${error instanceof Error ? error.message : "unknown error"}`,
          503,
        ),
      );
    });
  });

  return { state: "DRAFT_READY_MANUAL_SEND_REQUIRED", sha256: digest };
}

export function validateDraftContent(content) {
  const message = content.toString("utf8").replaceAll("\r\n", "\n");
  const headerEnd = message.indexOf("\n\n");
  const headers = headerEnd >= 0 ? message.slice(0, headerEnd) : message;
  if (!/^X-Unsent:\s*1\s*$/im.test(headers)) {
    throw new OutlookHandoffError("The EML artifact is not marked X-Unsent: 1.", 422);
  }
  const attachments = message.match(/^Content-Disposition:\s*attachment\b/gim) || [];
  if (attachments.length < 2) {
    throw new OutlookHandoffError("The EML draft must contain the mind map and PowerPoint.", 422);
  }
}