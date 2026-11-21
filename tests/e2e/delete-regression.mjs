import { chromium, webkit } from "playwright-core";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const fixtureUrl = `file://${root}/frontend/delete-regression-fixture.html`;
const executablePath = [process.env.CHROMIUM_PATH, "/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/chromium-browser"].filter(Boolean).find((candidate) => existsSync(candidate));
if (!executablePath) throw new Error("Kein unterstütztes Chromium gefunden");

const results = [];
const browserCases = [["Chromium", chromium, [["desktop", { width: 1440, height: 900 }], ["iphone", { width: 390, height: 844 }]]], ["WebKit", webkit, [["iphone", { width: 390, height: 844 }]]]].filter(([name]) => !process.env.DELETE_E2E_BROWSER || name === process.env.DELETE_E2E_BROWSER);
for (const [browserName, browserType, cases] of browserCases) {
  const browser = await browserType.launch({ headless: true, ...(browserType === chromium ? { executablePath, args: ["--no-sandbox"] } : {}) });
  try {
    for (const [viewportName, viewport] of cases) {
      const page = await browser.newPage({ viewport, isMobile: viewportName === "iphone" });
      const browserErrors = [];
      page.on("pageerror", (error) => browserErrors.push(error.message));
      await page.goto(fixtureUrl, { waitUntil: "domcontentloaded" });
      const panel = page.locator("smart-notification-manager-panel");
      const editor = panel.locator("smart-notification-rule-editor");
      const firstId = "11111111-1111-4111-8111-111111111111";
      const secondId = "22222222-2222-4222-8222-222222222222";
      await page.waitForFunction(() => document.querySelector("smart-notification-manager-panel")?.shadowRoot?.querySelector("smart-notification-rule-editor")?.shadowRoot?.querySelectorAll("[data-rule]").length === 2, null, { timeout: 5000 }).catch((error) => { throw new Error(`${viewportName}: initial list not rendered: ${browserErrors.join(" | ")} · ${error.message}`); });
      await panel.locator(`[data-rule='${firstId}']`).click();
      await editor.locator('[data-action="delete"]').click();
      if (await page.evaluate(() => window.__deleteCalls.length !== 0)) throw new Error(`${viewportName}: Löschrequest trotz abgelehnter Bestätigung gesendet`);
      const cancelled = await editor.evaluate((node) => node.getDeleteTrace());
      if (cancelled.confirmation !== "no" || cancelled.result !== "cancelled") throw new Error(`${viewportName}: Bestätigungsabbruch nicht im Delete-Trace`);

      await page.evaluate(() => { window.__confirmAnswer = true; });
      await editor.locator('[data-action="delete"]').click();
      await page.waitForFunction(() => document.querySelector("smart-notification-manager-panel")?.shadowRoot?.querySelector("smart-notification-rule-editor")?.shadowRoot?.querySelectorAll("[data-rule]").length === 1, null, { timeout: 5000 }).catch(async (error) => { const state = await page.evaluate(() => ({ calls: window.__deleteCalls, ws: window.__wsTypes, trace: document.querySelector("smart-notification-manager-panel")?.shadowRoot?.querySelector("smart-notification-rule-editor")?.getDeleteTrace?.(), html: document.querySelector("smart-notification-manager-panel")?.shadowRoot?.querySelector("smart-notification-rule-editor")?.shadowRoot?.innerHTML.slice(0, 300) })); throw new Error(`${viewportName}: delete did not refresh: ${JSON.stringify(state)} · ${browserErrors.join(" | ")} · ${error.message}`); });
      if (await page.locator("body").getAttribute("data-never") !== null) throw new Error("fixture marker");
      if (await panel.locator(`[data-rule='${firstId}']`).count() !== 0 || await panel.locator(`[data-rule='${secondId}']`).count() !== 1) throw new Error(`${viewportName}: falsche Regel gelöscht oder Doppelname gemeinsam entfernt`);
      if (await editor.locator('[data-field="name"]').count() !== 0) throw new Error(`${viewportName}: Editor nach erfolgreichem Löschen nicht geschlossen`);

      await panel.locator(`[data-rule='${secondId}']`).click();
      await page.evaluate(() => { window.__deleteDelay = 150; });
      await editor.evaluate((node) => { node.delete(); node.delete(); });
      await page.waitForFunction(() => document.querySelector("smart-notification-manager-panel")?.shadowRoot?.querySelector("smart-notification-rule-editor")?.shadowRoot?.querySelectorAll("[data-rule]").length === 0);
      const calls = await page.evaluate(() => window.__deleteCalls.slice());
      if (calls.filter((id) => id === secondId).length !== 1) throw new Error(`${viewportName}: Doppelklick-Schutz fehlgeschlagen`);
      await page.evaluate(async () => { window.__resetRules(); window.__deleteMode = "timeout"; window.__deleteDelay = 0; await document.querySelector("smart-notification-manager-panel").load(); });
      await page.waitForFunction(() => document.querySelector("smart-notification-manager-panel")?.shadowRoot?.querySelector("smart-notification-rule-editor")?.shadowRoot?.querySelectorAll("[data-rule]").length === 1);
      await panel.locator(`[data-rule='${firstId}']`).click();
      await editor.locator('[data-action="delete"]').click();
      await editor.locator('[role="alert"]').waitFor({ state: "visible", timeout: 5000 });
      if (await panel.locator(`[data-rule='${firstId}']`).count() !== 1) throw new Error(`${viewportName}: Regel trotz WebSocket-Timeout aus der Liste entfernt`);
      const timeoutTrace = await editor.evaluate((node) => node.getDeleteTrace());
      if (timeoutTrace.result !== "error" || timeoutTrace.websocket_response_received !== "no" || timeoutTrace.backend_persistence_confirmed !== "not_confirmed") throw new Error(`${viewportName}: Timeout nicht korrekt im Delete-Trace`);
      results.push({ browser: browserName, viewport: viewportName, duplicate_name_safe: true, confirmation_required: true, double_click_protected: true, timeout_preserves_rule: true });
      await page.close();
    }
  } finally { await browser.close(); }
}

console.log(JSON.stringify({ fixtureUrl, results }, null, 2));
