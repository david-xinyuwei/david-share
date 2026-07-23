import { describe, expect, it } from "vitest";
import { mkdir, mkdtemp, rm, symlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  createLocalAgentClient,
  resolveExistingInside,
  resolveInside,
  validateAgentName,
  validateArtifactPath,
  validateSessionId,
} from "./foundry-client.mjs";

describe("Local backend client boundaries", () => {
  it("accepts deployment-safe agent and session identifiers", () => {
    expect(validateAgentName("meeting-agent")).toBe("meeting-agent");
    expect(validateSessionId("session_1234")).toBe("session_1234");
  });

  it("requires the loopback backend and accepts Managed Agent mode", () => {
    expect(() => createLocalAgentClient({})).toThrow("MEETING_AGENT_LOCAL_AGENT_URL");
    expect(
      createLocalAgentClient({
        MEETING_AGENT_LOCAL_AGENT_URL: "http://127.0.0.1:18088",
        MEETING_AGENT_RUNTIME_MODE: "managed",
      }).mode,
    ).toBe("managed");
  });

  it("requires an explicit runtime attestation at the BFF boundary", async () => {
    const source = await import("node:fs/promises").then(({ readFile }) =>
      readFile(new URL("./index.mjs", import.meta.url), "utf8"),
    );
    expect(source).toContain("MEETING_AGENT_RUNTIME_ATTESTATION");
    expect(source).toContain("live-managed");
    expect(source).toContain("test-fixture");
    expect(source).toContain("/readiness");
    expect(source).toContain("backend_unavailable");
    expect(source).toContain("new AbortController()");
    expect(source).toContain('app.all("/api/{*splat}"');
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

  it("streams the local backend response without replaying the request", async () => {
    const originalFetch = globalThis.fetch;
    const calls = [];
    globalThis.fetch = async (url, options) => {
      calls.push({ url: String(url), options });
      return new Response('{"type":"accepted","data":{}}\n', {
        status: 200,
        headers: { "Content-Type": "application/x-ndjson" },
      });
    };
    try {
      const client = createLocalAgentClient({
        MEETING_AGENT_LOCAL_AGENT_URL: "http://127.0.0.1:18088",
        MEETING_AGENT_RUNTIME_MODE: "managed",
      });
      const response = await client.invokeStream(
        "session_1234",
        { schema_version: 1, operation: "build", events: [{}], recipients: [] },
      );

      expect(await response.text()).toContain('"type":"accepted"');
      expect(calls).toHaveLength(1);
      expect(calls[0].url).toContain("/invocations_stream?agent_session_id=session_1234");
      expect(calls[0].options.method).toBe("POST");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("does not retry a failed streaming request", async () => {
    const originalFetch = globalThis.fetch;
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      throw new Error("connection lost");
    };
    try {
      const client = createLocalAgentClient({
        MEETING_AGENT_LOCAL_AGENT_URL: "http://127.0.0.1:18088",
        MEETING_AGENT_RUNTIME_MODE: "managed",
      });
      await expect(
        client.invokeStream(
          "session_1234",
          { schema_version: 1, operation: "build", events: [{}], recipients: [] },
        ),
      ).rejects.toThrow("Streaming backend could not be reached");
      expect(calls).toBe(1);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});