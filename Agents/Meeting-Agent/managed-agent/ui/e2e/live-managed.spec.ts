import { expect, test } from "@playwright/test";
import path from "node:path";

test("builds a complete package through the deployed Managed Agent", async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(180_000);
  const expectedVersion = process.env.MANAGED_AGENT_VERSION;
  expect(expectedVersion).toBeTruthy();
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto("/");
  await expect(
    page.getByText("Foundry Prompt Agent · Managed GHCP", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".brand p")).toContainText(`v${expectedVersion}`);
  await expect(page.locator(".brand p")).toContainText("entra auth");

  await page.getByLabel("Final transcript").fill(
    "Project Atlas review confirmed the October 14 private preview.\n" +
      "Priya will prepare the security checklist by Friday.\n" +
      "The team decided that every outbound email remains subject to human review.\n" +
      "Open question: should the pilot include the regional support team?",
  );
  const stream = page.waitForResponse(
    (response) => response.url().endsWith("/api/runs/stream") && response.ok(),
    { timeout: 150_000 },
  );
  await page.getByRole("button", { name: "Generate meeting package" }).click();
  const streamResponse = await stream;
  expect(streamResponse.headers()["content-type"]).toContain("application/x-ndjson");

  await expect(page.locator('[data-stream-stage="complete"]')).toBeVisible({
    timeout: 150_000,
  });
  await expect(page.locator(".stream-steps li.done")).toHaveCount(6);
  await expect(page.locator(".result-heading h2")).toBeVisible();
  await expect(page.locator(".mind-map img")).toBeVisible();
  await expect(page.locator(".stream-output")).not.toContainText('{"fixture":true}');

  const analysisHref = await page.getByRole("link", { name: "Analysis JSON" }).getAttribute("href");
  const presentationHref = await page.getByRole("link", { name: "PowerPoint" }).getAttribute("href");
  const emlHref = await page.getByRole("link", { name: "EML draft" }).getAttribute("href");
  expect(analysisHref).toBeTruthy();
  expect(presentationHref).toBeTruthy();
  expect(emlHref).toBeTruthy();

  const analysis = await (await request.get(analysisHref!)).json();
  expect(JSON.stringify(analysis)).toContain("October 14");
  expect(JSON.stringify(analysis)).toContain("Priya");
  expect(JSON.stringify(analysis)).toContain("human review");
  const presentation = await request.get(presentationHref!);
  expect((await presentation.body()).subarray(0, 2).toString("ascii")).toBe("PK");
  const eml = await (await request.get(emlHref!)).text();
  expect(eml).toContain("X-Unsent: 1");
  expect(eml).toContain('filename="mind-map.png"');
  expect(eml).toContain('filename="meeting-summary.pptx"');
  expect(consoleErrors).toEqual([]);

  await page.screenshot({
    path: testInfo.outputPath("ui-live-desktop.png"),
    fullPage: true,
  });
  testInfo.annotations.push({
    type: "runtime",
    description: `managed-agent-v${expectedVersion}`,
  });
});