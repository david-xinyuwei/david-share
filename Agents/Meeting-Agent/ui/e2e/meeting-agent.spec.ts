import { expect, test } from "@playwright/test";
import path from "node:path";

test("generates distinct meeting packages and downloadable artifacts", async ({ page, request }, testInfo) => {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (failed) => failedRequests.push(failed.url()));

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Meeting Agent" })).toBeVisible();
  await expect(page.getByText("Offline contract test", { exact: true })).toBeVisible();

  await page.getByLabel("Final transcript").fill(
    "The product council approved the September pilot.\n" +
      "Mina will prepare the security checklist before Friday.\n" +
      "Should the pilot include the regional support team?",
  );
  await page.getByRole("button", { name: "Generate meeting package" }).click();
  await expect(page.locator(".result-heading h2")).toContainText("September pilot");
  const firstRun = await page.locator(".run-id").textContent();
  await expect(page.locator(".mind-map svg, .mind-map img")).toBeVisible();

  await page.getByLabel("Final transcript").fill(
    "Operations found database latency in the reporting service.\n" +
      "Bob will tune the index before Monday.\n" +
      "The team agreed to monitor error rates every hour.",
  );
  await page.getByRole("button", { name: "Generate meeting package" }).click();
  await expect(page.locator(".result-heading h2")).toContainText("database latency");
  const secondRun = await page.locator(".run-id").textContent();
  expect(secondRun).not.toBe(firstRun);

  const presentationHref = await page.getByRole("link", { name: "PowerPoint" }).getAttribute("href");
  const emlHref = await page.getByRole("link", { name: "EML draft" }).getAttribute("href");
  expect(presentationHref).toBeTruthy();
  expect(emlHref).toBeTruthy();
  const presentation = await request.get(presentationHref!);
  const eml = await request.get(emlHref!);
  expect(presentation.ok()).toBeTruthy();
  expect((await presentation.body()).subarray(0, 2).toString("ascii")).toBe("PK");
  expect(eml.ok()).toBeTruthy();
  expect((await eml.text())).toContain("X-Unsent: 1");

  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);

  if (testInfo.project.name === "desktop") {
    await page.screenshot({
      path: path.resolve(process.cwd(), "../images/meeting-agent-ui.png"),
      fullPage: true,
    });
  }
});

test("rejects malformed provider JSONL without replacing the previous result", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Final transcript").fill("The team approved the release plan.");
  await page.getByRole("button", { name: "Generate meeting package" }).click();
  await expect(page.locator(".result-heading h2")).toContainText("approved the release plan");

  await page.getByRole("button", { name: "Provider JSONL" }).click();
  await page.getByLabel("Provider event stream").fill('{"event_id":"valid-json"}\nnot-json');
  await page.getByRole("button", { name: "Generate meeting package" }).click();

  await expect(page.getByRole("alert")).toContainText("Provider JSONL line 2 is not valid JSON");
  await expect(page.locator(".result-heading h2")).toContainText("approved the release plan");
});