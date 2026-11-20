import { chromium } from "playwright-core";
import { existsSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const artifactDir = path.join(root, "artifacts", "phase12-browser");
const baseUrl = process.env.PHASE12_BASE_URL || `file://${root}/frontend/phase-12-statistics-fixture.html`;
const storageState = process.env.PHASE12_STORAGE_STATE || undefined;
const chromiumCandidates = [
  process.env.CHROMIUM_PATH,
  "/usr/bin/chromium",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium-browser",
].filter(Boolean);
const executablePath = chromiumCandidates.find((candidate) => existsSync(candidate));
if (!executablePath) {
  throw new Error(`Kein unterstütztes Chromium gefunden. Geprüft: ${chromiumCandidates.join(", ")}`);
}
const browser = await chromium.launch({ executablePath, headless: true, args: ["--no-sandbox"] });

await mkdir(artifactDir, { recursive: true });
const viewports = { desktop: { width: 1440, height: 900 }, ipad: { width: 1024, height: 1366 }, iphone: { width: 390, height: 844 } };
const results = [];

try {
  for (const [name, viewport] of Object.entries(viewports)) {
    const context = await browser.newContext({ viewport, storageState });
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
    const page = await context.newPage();
    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "Alarmstatistiken" }).waitFor();
    await page.locator('[data-viewport="' + name + '"]').waitFor();
    await page.screenshot({ path: path.join(artifactDir, `statistics-${name}.png`), fullPage: true });
    await context.tracing.stop({ path: path.join(artifactDir, `statistics-${name}.trace.zip`) });
    results.push({ viewport: name, url: page.url(), title: await page.title() });
    await context.close();
  }
  console.log(JSON.stringify({ baseUrl, results }, null, 2));
} finally {
  await browser.close();
}
