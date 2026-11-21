import { chromium, webkit } from "playwright-core";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const fixtureUrl = `file://${root}/frontend/rule-validation-fixture.html`;
const executablePath = [process.env.CHROMIUM_PATH, "/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/chromium-browser"].filter(Boolean).find((candidate) => existsSync(candidate));
if (!executablePath) throw new Error("Kein unterstütztes Chromium gefunden");

const results = [];
for (const [browserName, browserType, cases] of [["Chromium", chromium, [["desktop", { width: 1440, height: 900 }], ["iphone", { width: 390, height: 844 }]]], ["WebKit", webkit, [["iphone", { width: 390, height: 844 }]]]]) {
  const browser = await browserType.launch({ headless: true, ...(browserType === chromium ? { executablePath, args: ["--no-sandbox"] } : {}) });
  try {
    for (const [name, viewport] of cases) {
      const page = await browser.newPage({ viewport, isMobile: name === "iphone" });
    await page.goto(fixtureUrl, { waitUntil: "domcontentloaded" });
    const editor = page.locator("smart-notification-rule-editor");
    await editor.locator('[data-field="name"]').fill("Haustür noch offen");
    await editor.locator('[data-field="area_id"]').selectOption("eingang");
    await editor.locator('[data-field="priority"]').selectOption("warning");
    await editor.locator('[data-trigger-field="to_state"]').fill("on");
    await editor.locator('[data-trigger-field="minimum_duration_seconds"]').fill("120");
    await editor.locator('[data-trigger-entity="binary_sensor.haustur_door_sensor"]').check();
    const preview = await editor.locator(".preview p").textContent();
    if (!preview.includes("Door sensor im Bereich Eingang") || !preview.includes("mindestens 120 Sekunden") || preview.includes("Empfänger") || preview.includes("Zustellung")) throw new Error(`${name}: Vorschau ist nicht semantisch korrekt`);
    await editor.locator('[data-action="save"]').click();
    if (await page.locator("body").getAttribute("data-saved") !== "passed" || await page.locator("body").getAttribute("data-conditions") !== "0") throw new Error(`${name}: Regel ohne Bedingungen wurde nicht gespeichert`);
    results.push({ browser: browserName, viewport: name, saved_without_conditions: true, preview });
    await page.close();
    }
  } finally {
    await browser.close();
  }
}
console.log(JSON.stringify({ fixtureUrl, results }, null, 2));
