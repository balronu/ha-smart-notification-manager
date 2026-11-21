import { chromium, webkit } from "playwright-core";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const fixtureUrl = `file://${root}/frontend/panel-lifecycle-fixture.html`;
const executablePath = [process.env.CHROMIUM_PATH, "/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/chromium-browser"].filter(Boolean).find((candidate) => existsSync(candidate));
if (!executablePath) throw new Error("Kein unterstütztes Chromium gefunden");

const run = async (browserType, name, options = {}) => {
  const browser = await browserType.launch({ headless: true, ...(browserType === chromium ? { executablePath, args: ["--no-sandbox"] } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, deviceScaleFactor: 2 });
  await page.goto(fixtureUrl, { waitUntil: "domcontentloaded" });
  const panel = page.locator("smart-notification-manager-panel");
  const editor = panel.locator("smart-notification-rule-editor");
  const navigation = panel.getByRole("navigation", { name: "Home Assistant Navigation" });
  const home = navigation.getByRole("link", { name: "Zur Übersicht" });
  await home.waitFor();
  if (await home.getAttribute("href") !== "/home/overview") throw new Error("HA-Standardübersicht wurde nicht aus systemData abgeleitet");

  await editor.locator('[data-action="new"]').first().click();
  await editor.locator('[data-field="name"]').fill("Ungespeicherter mobiler Entwurf");
  let dialogSeen = false;
  page.once("dialog", async (dialog) => { dialogSeen = true; await dialog.dismiss(); });
  await home.click();
  if (!dialogSeen) throw new Error("Navigation ohne Draft-Bestätigung");
  if (await editor.locator('[data-field="name"]').inputValue() !== "Ungespeicherter mobiler Entwurf") throw new Error("Draft wurde trotz Abbruch verworfen");

  const before = await navigation.boundingBox();
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const after = await navigation.boundingBox();
  if (!before || !after || after.y < -1 || after.y > 8) throw new Error("Mobile Notfallnavigation bleibt beim langen Formular nicht erreichbar");
    return { browser: name, viewport: "iphone", overviewHref: "/home/overview", draftGuard: true, stickyNavigation: true };
  } finally {
    await browser.close();
  }
};

const results = [
  await run(chromium, "Chromium Mobile"),
  await run(webkit, "WebKit Mobile"),
];
console.log(JSON.stringify({ fixtureUrl, results }, null, 2));
