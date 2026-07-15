import { describe, expect, it } from "vitest";

import {
  buildAzureCliCredentialOptions,
  parseAzdValues,
  resolveInside,
  validateAgentName,
  validateArtifactPath,
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

  it("rejects artifact traversal and files outside generated runs", () => {
    expect(() => validateArtifactPath("../password.txt")).toThrow("Artifact path is invalid");
    expect(() => validateArtifactPath("uploads/private.eml")).toThrow("Artifact path is invalid");
    expect(() => resolveInside("/workspace/safe", "../outside.eml")).toThrow(
      "escapes the session directory",
    );
  });

  it("accepts only generated artifact paths", () => {
    const value = "artifacts/0123456789abcdef01234567/meeting-summary.pptx";
    expect(validateArtifactPath(value)).toBe(value);
    expect(resolveInside("/workspace/safe", value)).toBe(
      "/workspace/safe/artifacts/0123456789abcdef01234567/meeting-summary.pptx",
    );
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