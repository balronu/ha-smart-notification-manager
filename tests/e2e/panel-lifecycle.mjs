import { chromium } from "playwright-core";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const fixtureUrl = `file://${root}/frontend/panel-lifecycle-fixture.html`;
const executablePath = [process.env.CHROMIUM_PATH, "/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/chromium-browser"].filter(Boolean).find((candidate) => existsSync(candidate));
if (!executablePath) throw new Error("Kein unterstütztes Chromium gefunden");

const browser = await chromium.launch({executablePath, headless: true, args: ["--no-sandbox"]});
try {
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  await page.goto(fixtureUrl, {waitUntil: "domcontentloaded"});
  const panel = page.locator("smart-notification-manager-panel");
  const editor = panel.locator("smart-notification-rule-editor");
  await editor.locator('[data-action="new"]').first().click();
  const name = editor.locator('[data-field="name"]');
  await name.evaluate((element) => {
    const formRoot = element.closest(".editor");
    let mutations = 0;
    const observer = new MutationObserver(() => { mutations += 1; });
    observer.observe(formRoot, {childList: true, subtree: true});
    window.__focusProbe = {element, observer, get mutations() { return mutations; }};
  });
  await name.focus();
  await page.keyboard.type("Frischer Entwurf bleibt stabil");
  await page.evaluate(() => window.__reloadPanel());
  await page.evaluate(() => {
    for (let index = 0; index < 5; index += 1) window.__panel.hass = {connection: window.__panel._hass.connection, callWS: window.__panel._hass.callWS};
  });
  await page.waitForTimeout(320);
  if (await name.inputValue() !== "Frischer Entwurf bleibt stabil") throw new Error("Eingabe nach verspäteter Panel-Antwort verloren");
  if (!(await name.evaluate((element) => element === window.__focusProbe.element))) throw new Error("Aktives Eingabeelement wurde ersetzt");
  if (!(await name.evaluate((element) => element === element.getRootNode().activeElement))) throw new Error("Fokus ging nach Panel-Update verloren");
  const mutationCount = await page.evaluate(() => { window.__focusProbe.observer.disconnect(); return window.__focusProbe.mutations; });
  if (mutationCount !== 0) throw new Error(`Formular-DOM wurde während der Eingabe verändert (${mutationCount})`);
  console.log(JSON.stringify({fixtureUrl, inputPreserved: true, activeElementPreserved: true, formMutations: mutationCount}, null, 2));
} finally {
  await browser.close();
}
