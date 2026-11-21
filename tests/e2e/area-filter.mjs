import { chromium, webkit } from "playwright-core";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const fixtureUrl = `file://${root}/frontend/area-filter-fixture.html`;
const executablePath = [process.env.CHROMIUM_PATH, "/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/chromium-browser"].filter(Boolean).find((candidate) => existsSync(candidate));
if (!executablePath) throw new Error("Kein unterstütztes Chromium gefunden");

const run = async (name, browserType, viewport, options = {}) => {
  const browser = await browserType.launch({ headless: true, ...(browserType === chromium ? { executablePath, args: ["--no-sandbox"] } : {}) });
  try {
    const page = await browser.newPage({ viewport, isMobile: options.isMobile || false });
    await page.goto(fixtureUrl, { waitUntil: "domcontentloaded" });
    const editor = page.locator("smart-notification-rule-editor");
    await editor.locator('[data-field="area_id"]').selectOption("kitchen");
    const picker = editor.locator('[data-entity-picker="0"]');
    if (await picker.locator('[data-trigger-entity="sensor.kitchen_temperature_long_identifier"]').count() !== 1) throw new Error("Küchen-Entität fehlt im Standardfilter");
    if (await picker.locator('[data-trigger-entity="binary_sensor.living_window"]').count() !== 0) throw new Error("Wohnzimmer-Entität wird im Küchenfilter angezeigt");
    await editor.locator('[data-field="entity-area-filter"]').selectOption("");
    if (await picker.locator('[data-trigger-entity="binary_sensor.living_window"]').count() !== 1) throw new Error("Alle Bereiche zeigt nicht alle Entitäten");
    await picker.locator('[data-trigger-entity="binary_sensor.living_window"]').check();
    await editor.locator('[data-field="area_id"]').selectOption("living");
    if (await editor.locator('[data-field="entity-area-filter"]').inputValue() !== "") throw new Error("Bewusste Filterabweichung wurde überschrieben");
    if (!(await picker.locator('[data-trigger-entity="binary_sensor.living_window"]').isChecked())) throw new Error("Auswahl wurde beim Bereichswechsel verändert");
    await editor.locator('[data-field="entity-area-filter"]').selectOption("__rule_area__");
    await editor.locator('[data-field="area_id"]').selectOption("kitchen");
    if (await picker.locator('[data-trigger-entity="sensor.kitchen_temperature_long_identifier"]').count() !== 1) throw new Error("Regelbereich wurde nicht als Standardfilter verwendet");
    await editor.locator('[data-field="entity-search"]').fill("long_identifier");
    if (await picker.locator('[data-trigger-entity="sensor.kitchen_temperature_long_identifier"]').count() !== 1) throw new Error("Suche funktioniert nicht innerhalb des Bereichsfilters");
    if ((await picker.locator('[data-trigger-entity="sensor.kitchen_temperature_long_identifier"]').evaluate((node) => node.parentElement.innerText)).length < 20) throw new Error("Lange Entity-ID wird nicht verständlich dargestellt");
    await page.close();
    return { browser: name, viewport };
  } finally {
    await browser.close();
  }
};

const results = [];
results.push(await run("Chromium Desktop", chromium, { width: 1440, height: 900 }));
results.push(await run("Chromium Mobile", chromium, { width: 390, height: 844 }, { isMobile: true }));
results.push(await run("WebKit Mobile", webkit, { width: 390, height: 844 }, { isMobile: true }));
console.log(JSON.stringify({ fixtureUrl, result: "area-filter passed", browsers: results }, null, 2));
