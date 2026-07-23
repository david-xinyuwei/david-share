import { expect, test, type Download } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { mindMapRichText } from "../src/mind-map-export";

test("generates distinct meeting packages and downloadable artifacts", async ({
  page,
  request,
  context,
}, testInfo) => {
  const consoleErrors: string[] = [];
  const failedRequests: Array<{ url: string; error: string | undefined }> = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (failed) =>
    failedRequests.push({ url: failed.url(), error: failed.failure()?.errorText }),
  );
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Meeting Agent" })).toBeVisible();
  await expect(page.getByText("Test fixture", { exact: true })).toBeVisible();

  await page.getByLabel("Final transcript").fill(
    "The product council approved the September pilot.\n" +
      "Mina will prepare the security checklist before Friday.\n" +
      "Should the pilot include the regional support team?",
  );
  const firstStream = page.waitForResponse(
    (response) => response.url().endsWith("/api/runs/stream") && response.ok(),
  );
  await page.getByRole("button", { name: "Generate meeting package" }).click();
  const firstStreamResponse = await firstStream;
  expect(firstStreamResponse.headers()["content-type"]).toContain("application/x-ndjson");
  await expect(page.locator(".result-heading h2")).toBeVisible();
  const firstTitle = await page.locator(".result-heading h2").textContent();
  const firstRun = await page.locator(".run-id").textContent();
  await expect(page.locator(".mind-map img")).toBeVisible();
  await expect(page.locator(".mind-map svg")).toHaveCount(0);
  await expect(page.locator('[data-stream-stage="complete"]')).toBeVisible();
  await expect(page.getByRole("button", { name: "Generate meeting package" })).toBeEnabled();

  await page.getByLabel("Final transcript").fill(
    "Operations found database latency in the reporting service.\n" +
      "Bob will tune the index before Monday.\n" +
      "The team agreed to monitor error rates every hour.",
  );
  await page.getByRole("button", { name: "Generate meeting package" }).click();
  await expect(page.locator(".result-heading h2")).toBeVisible();
  await expect(page.locator('[data-stream-stage="complete"]')).toBeVisible();
  await expect(page.locator(".stream-steps li.done")).toHaveCount(6);
  await expect(page.getByRole("button", { name: "Generate meeting package" })).toBeEnabled();
  const secondRun = await page.locator(".run-id").textContent();
  const secondTitle = await page.locator(".result-heading h2").textContent();
  expect(secondRun).not.toBe(firstRun);
  expect(secondTitle).not.toBe(firstTitle);

  const presentationHref = await page.getByRole("link", { name: "PowerPoint" }).getAttribute("href");
  const emlHref = await page.getByRole("link", { name: "EML draft" }).getAttribute("href");
  const analysisHref = await page.getByRole("link", { name: "Analysis JSON" }).getAttribute("href");
  const mermaidHref = await page.getByRole("link", { name: "Mermaid source" }).getAttribute("href");
  const mindMapHref = await page.locator(".mind-map img").getAttribute("src");
  const pngHref = await page.getByRole("link", { name: "Save PNG" }).getAttribute("href");
  expect(presentationHref).toBeTruthy();
  expect(emlHref).toBeTruthy();
  expect(analysisHref).toBeTruthy();
  expect(mermaidHref).toBeTruthy();
  expect(pngHref).toBe(mindMapHref);
  const presentation = await request.get(presentationHref!);
  const eml = await request.get(emlHref!);
  const analysis = await request.get(analysisHref!);
  const mermaid = await request.get(mermaidHref!);
  expect(presentation.ok()).toBeTruthy();
  expect((await presentation.body()).subarray(0, 2).toString("ascii")).toBe("PK");
  expect(eml.ok()).toBeTruthy();
  const emlText = await eml.text();
  expect(emlText).toContain("X-Unsent: 1");
  expect(emlText).toContain("cid:meeting-mind-map");
  expect(emlText).toContain("Content-Disposition: inline");
  expect(analysis.ok()).toBeTruthy();
  const [pngDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Save PNG" }).click(),
  ]);
  const png = await downloadBuffer(pngDownload);
  expect(png.subarray(1, 4).toString("ascii")).toBe("PNG");
  expect(mermaid.ok()).toBeTruthy();
  const mermaidText = await mermaid.text();
  expect(mermaidText).toMatch(/^mindmap\n/);

  await page.getByRole("button", { name: "Copy rich text" }).click();
  await expect(page.getByRole("status")).toContainText("Mind map rich text copied");
  const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
  const analysisJson = await analysis.json();
  const expectedClipboard = mindMapRichText(analysisJson.mind_map).text;
  const mermaidNodeCount = mermaidText.split(/\r?\n/).slice(1).filter((line) => line.trim()).length;
  const actualLines = clipboardText.split("\n");
  const expectedLines = expectedClipboard.split("\n");
  expect(actualLines.map((line) => line.trim())).toEqual(
    expectedLines.map((line) => line.trim()),
  );
  expectedLines.forEach((line, index) => {
    const expectedDepth = line.match(/^\t*/)?.[0].length || 0;
    const actualIndent = actualLines[index].match(/^\s*/)?.[0].length || 0;
    expect(actualIndent).toBeGreaterThanOrEqual(expectedDepth);
  });
  expect(actualLines).toHaveLength(mermaidNodeCount);

  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
  const streamTransfers = await page.evaluate(() =>
    performance
      .getEntriesByType("resource")
      .filter((entry) => entry.name.endsWith("/api/runs/stream"))
      .map((entry) => {
        const resource = entry as PerformanceResourceTiming;
        return {
          responseEnd: resource.responseEnd,
          responseStatus: resource.responseStatus,
          transferSize: resource.transferSize,
        };
      }),
  );
  expect(streamTransfers).toHaveLength(2);
  for (const transfer of streamTransfers) {
    expect(transfer.responseStatus).toBe(200);
    expect(transfer.responseEnd).toBeGreaterThan(0);
    expect(transfer.transferSize).toBeGreaterThan(0);
  }
  expect(consoleErrors).toEqual([]);
  expect(
    failedRequests.filter(
      (failure) =>
        !failure.url.endsWith("/api/runs/stream") || failure.error !== "net::ERR_ABORTED",
    ),
  ).toEqual([]);

  if (testInfo.project.name === "desktop") {
    await page.screenshot({
      path: path.resolve(process.cwd(), "../.azure/validation/test-fixture-ui-e2e.png"),
      fullPage: true,
    });
  }
});

test("rejects malformed ASR JSONL without replacing the previous result", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Final transcript").fill("The team approved the release plan.");
  await page.getByRole("button", { name: "Generate meeting package" }).click();
  const previousTitle = await page.locator(".result-heading h2").textContent();

  await page.getByRole("button", { name: "ASR JSONL" }).click();
  await page.getByLabel("Normalized ASR event stream").fill(
    '{"event_id":"valid-json"}\nnot-json',
  );
  await page.getByRole("button", { name: "Generate meeting package" }).click();

  await expect(page.getByRole("alert")).toContainText("ASR JSONL line 2 is not valid JSON");
  await expect(page.locator(".result-heading h2")).toHaveText(previousTitle || "");
});

async function downloadBuffer(download: Download): Promise<Buffer> {
  const path = await download.path();
  if (!path) throw new Error("The browser did not persist the PNG download.");
  return readFile(path);
}