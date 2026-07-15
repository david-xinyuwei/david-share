import { describe, expect, it } from "vitest";
import { mkdir, mkdtemp, rm, symlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  buildAzureCliCredentialOptions,
  parseAzdValues,
  resolveExistingInside,
  resolveInside,
  validateAgentName,
  validateArtifactPath,
  validateRuntimeMode,
  validateSessionId,
} from "./foundry-client.mjs";

describe("Foundry client boundaries", () => {
  it("binds Azure CLI authentication to the selected tenant and subscription", () => {
    expect(
      buildAzureCliCredentialOptions({
        AZURE_TENANT_ID: "11111111-2222-3333-4444-555555555555",
        AZURE_SUBSCRIPTION_ID: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      }),
    ).toEqual({
      subscription: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    });
    expect(() => buildAzureCliCredentialOptions({})).toThrow("AZURE_TENANT_ID");
    expect(() =>
      buildAzureCliCredentialOptions({
        AZURE_TENANT_ID: "wrong-tenant",
        AZURE_SUBSCRIPTION_ID: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      }),
    ).toThrow("AZURE_TENANT_ID");
  });

  it("accepts deployment-safe agent and session identifiers", () => {
    expect(validateAgentName("meeting-agent")).toBe("meeting-agent");
    expect(validateSessionId("session_1234")).toBe("session_1234");
  });

  it("distinguishes direct AOAI, offline, and Foundry runtime modes", () => {
    expect(validateRuntimeMode("aoai", "http://127.0.0.1:18088")).toBe("aoai");
    expect(validateRuntimeMode(undefined, "http://127.0.0.1:18088")).toBe("local");
    expect(validateRuntimeMode("aoai", null)).toBe("foundry");
    expect(() => validateRuntimeMode("unsupported", "http://127.0.0.1:18088")).toThrow(
      "local or aoai",
    );
  });

  it("rejects artifact traversal and files outside generated runs", () => {
    expect(() => validateArtifactPath("../password.txt")).toThrow("Artifact path is invalid");
    expect(() => validateArtifactPath("uploads/private.eml")).toThrow("Artifact path is invalid");
    expect(() => validateArtifactPath("artifacts/01234567/payload.exe")).toThrow(
      "Artifact path is invalid",
    );
    expect(() => resolveInside("/workspace/safe", "../outside.eml")).toThrow(
      "escapes the session directory",
    );
  });

  it("accepts only generated artifact paths", () => {
    const value = "artifacts/0123456789abcdef01234567/meeting-summary.pptx";
    expect(validateArtifactPath(value)).toBe(value);
    expect(resolveInside("/workspace/safe", value)).toBe(
      path.resolve("/workspace/safe", value),
    );
  });

  it("rejects generated artifact paths that resolve through a link outside the session", async () => {
    const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), "meeting-agent-path-"));
    const sessionRoot = path.join(temporaryRoot, "session");
    const outsideRoot = path.join(temporaryRoot, "outside");
    const runId = "0123456789abcdef01234567";
    await mkdir(path.join(sessionRoot, "artifacts"), { recursive: true });
    await mkdir(outsideRoot, { recursive: true });
    await writeFile(path.join(outsideRoot, "meeting-analysis.json"), "{}", "utf8");
    await symlink(
      outsideRoot,
      path.join(sessionRoot, "artifacts", runId),
      process.platform === "win32" ? "junction" : "dir",
    );
    try {
      await expect(
        resolveExistingInside(
          sessionRoot,
          `artifacts/${runId}/meeting-analysis.json`,
        ),
      ).rejects.toThrow("escapes the session directory");
    } finally {
      await rm(temporaryRoot, { recursive: true, force: true });
    }
  });

  it("reads azd values as data without evaluating shell syntax", () => {
    expect(
      parseAzdValues(
        'AZURE_AI_PROJECT_ENDPOINT="https://example.services.ai.azure.com/api/projects/demo"\n' +
          'AGENT_MEETING_AGENT_NAME="meeting-agent"\n' +
          'IGNORED=$(touch /tmp/never-run)\n',
      ),
    ).toEqual({
      AZURE_AI_PROJECT_ENDPOINT: "https://example.services.ai.azure.com/api/projects/demo",
      AGENT_MEETING_AGENT_NAME: "meeting-agent",
      IGNORED: "$(touch /tmp/never-run)",
    });
  });
});