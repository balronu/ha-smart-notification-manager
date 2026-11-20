import { chromium } from "playwright-core";
import { existsSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const artifactDir = path.join(root, "artifacts", "editor-select");
const fixtureUrl = `file://${root}/frontend/phase-2-fixture.html`;
const executablePath = [process.env.CHROMIUM_PATH, "/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/chromium-browser"].filter(Boolean).find((candidate) => existsSync(candidate));
if (!executablePath) throw new Error("Kein unterstütztes Chromium gefunden");

await mkdir(artifactDir, { recursive: true });
const browser = await chromium.launch({ executablePath, headless: true, args: ["--no-sandbox"] });
const viewports = { desktop: { width: 1440, height: 900 }, ipad: { width: 1024, height: 1366 }, iphone: { width: 390, height: 844 } };
const results = [];

try {
  for (const [name, viewport] of Object.entries(viewports)) {
    const context = await browser.newContext({ viewport });
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
    const page = await context.newPage();
    await page.goto(fixtureUrl, { waitUntil: "domcontentloaded" });
    const editor = page.locator("smart-notification-rule-editor");
    await editor.locator('[data-action="new"]').first().click();
    const area = editor.locator('[data-field="area_id"]');
    const priority = editor.locator('[data-field="priority"]');
    await area.selectOption("wohnzimmer");
    await priority.selectOption("critical");
    await editor.evaluate((element) => {
      const select = element.shadowRoot.querySelector('[data-field="priority"]');
      select.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, composed: true }));
      element.data = { rules: element._rules, entities: element._entities };
    });
    await page.waitForTimeout(10);
    await page.screenshot({ path: path.join(artifactDir, `editor-${name}.png`), fullPage: true });
    if (await area.inputValue() !== "wohnzimmer" || await priority.inputValue() !== "critical") throw new Error(`${name}: Auswahl nach Hintergrundaktualisierung verloren`);
    await editor.evaluate((element) => element.shadowRoot.querySelector('[data-field="priority"]').dispatchEvent(new PointerEvent("pointerup", { bubbles: true, composed: true })));
    await page.waitForTimeout(10);
    if (await area.inputValue() !== "wohnzimmer" || await priority.inputValue() !== "critical") throw new Error(`${name}: Auswahl nach Pointerup verloren`);
    await context.tracing.stop({ path: path.join(artifactDir, `editor-${name}.trace.zip`) });
    results.push({ viewport: name, area: await area.inputValue(), priority: await priority.inputValue() });
    await context.close();
  }
  console.log(JSON.stringify({ fixtureUrl, results }, null, 2));
} finally {
  await browser.close();
}
