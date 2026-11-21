import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { once } from "node:events";
import { chromium, webkit } from "playwright-core";

const root = new URL("../..", import.meta.url).pathname;
const diagnosticsSource = await readFile(`${root}/custom_components/smart_notification_manager/diagnostics.py`, "utf8");
const diagnosticsHtml = diagnosticsSource.match(/DIAGNOSTIC_HTML = r"""([\s\S]*?)"""/)[1];
const panelScript = await readFile(`${root}/custom_components/smart_notification_manager/frontend/smart-notification-manager.js`, "utf8");

const server = createServer((request, response) => {
  if (request.url.startsWith("/api/smart_notification_manager/diagnostics")) {
    response.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" });
    response.end(diagnosticsHtml);
    return;
  }
  if (request.url.startsWith("/smart_notification_manager_static/smart-notification-manager.js")) {
    response.writeHead(200, { "content-type": "text/javascript; charset=utf-8" });
    response.end(panelScript);
    return;
  }
  if (request.url === "/favicon.ico") { response.writeHead(204); response.end(); return; }
  response.writeHead(404);
  response.end("not found");
});

server.on("upgrade", (request, socket) => {
  if (request.url !== "/api/websocket") { socket.destroy(); return; }
  const accept = createHash("sha1").update(`${request.headers["sec-websocket-key"]}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`).digest("base64");
  socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
  const payload = Buffer.from(JSON.stringify({ type: "auth_required", ha_version: "2026.11.2" }));
  socket.write(Buffer.concat([Buffer.from([0x81, payload.length]), payload]));
  socket.end();
});

server.listen(0, "127.0.0.1");
await once(server, "listening");
const { port } = server.address();
const url = `http://127.0.0.1:${port}/api/smart_notification_manager/diagnostics`;

const run = async (name, browserType, options = {}) => {
  const launchOptions = { headless: true };
  if (browserType === chromium) launchOptions.executablePath = "/usr/bin/chromium";
  const browser = await browserType.launch(launchOptions);
  try {
    const page = await browser.newPage({ viewport: options.viewport || { width: 1280, height: 900 }, isMobile: options.isMobile || false });
    const pageErrors = [];
    const consoleErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
    await page.goto(url, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Diagnose starten" }).click();
    await page.waitForFunction(() => document.querySelector("#summary")?.textContent !== "Noch nicht gestartet.", null, { timeout: 8000 });
    const statuses = await page.locator("#checks .status").allTextContents();
    const body = await page.locator("body").innerText();
    const summary = await page.locator("#summary").innerText();
    if (!body.includes("Panel-Ressource") || !body.includes("Panel-Initialisierung") || !body.includes("HA-WebSocket")) throw new Error("Prüfungen fehlen");
    if (!summary.startsWith("Diagnose abgeschlossen")) throw new Error(`Diagnose nicht abgeschlossen: ${summary}`);
    if (statuses[0] !== "OK" || statuses[1] !== "OK" || statuses[2] !== "OK") throw new Error(`Diagnoseprüfung fehlgeschlagen: ${statuses.join(", ")} · ${body}`);
    if (pageErrors.length || consoleErrors.length) throw new Error(`Unerwartete Browserfehler: ${[...pageErrors, ...consoleErrors].join(" | ")}`);

    await page.evaluate(async () => {
      const panel = document.createElement("smart-notification-manager-panel");
      if (panel.hasAttribute("data-snm-build")) throw new Error("Panel trägt beim Konstruktor bereits Attribute");
      panel.style.display = "block";
      panel.style.width = "100%";
      document.body.append(panel);
      panel.hass = {
        connection: {},
        callWS: async (message) => message.type === "smart_notification_manager/list"
          ? { rules: [], entities: [{ entity_id: "sensor.test", friendly_name: "Test", area_id: "area", area_name: "Wohnzimmer", state: "on" }] }
          : { recipients: [], groups: [], channels: [], totals: {}, daily: {}, monthly: {} },
      };
      await panel.load();
      panel._editor.data = { rules: [], entities: [{ entity_id: "sensor.test", friendly_name: "Test", area_id: "area", area_name: "Wohnzimmer", state: "on" }] };
      window.__beta6Panel = panel;
    });
    const panel = page.locator("smart-notification-manager-panel").last();
    const editor = panel.locator("smart-notification-rule-editor").last();
    if (!(await editor.evaluate((element) => element.shadowRoot?.childElementCount > 0))) throw new Error(`${name}: erster sichtbarer Editor-Render fehlt`);
    await editor.locator('[data-action="new"]').first().click({ force: true });
    const nameField = editor.locator('[data-field="name"]');
    await nameField.focus({ force: true });
    await page.keyboard.type("Beta 6 Entwurf");
    if (await nameField.inputValue() !== "Beta 6 Entwurf") throw new Error(`${name}: Texteingabe verloren`);
    await editor.locator('[data-field="area_id"]').selectOption("area", { force: true });
    await editor.locator('[data-field="priority"]').selectOption("critical", { force: true });
    if (await editor.locator('[data-field="area_id"]').inputValue() !== "area" || await editor.locator('[data-field="priority"]').inputValue() !== "critical") throw new Error(`${name}: Dropdown-Auswahl verloren`);
    console.log(JSON.stringify({ browser: name, statuses, customElementCreate: true, initialRender: true, buildId: await panel.getAttribute("data-snm-build"), focus: true, dropdowns: true, consoleErrors }));
  } finally {
    await browser.close();
  }
};

try {
  await run("Chromium Desktop", chromium);
  await run("Chromium Mobile", chromium, { viewport: { width: 390, height: 844 }, isMobile: true });
  await run("WebKit Mobile", webkit, { viewport: { width: 390, height: 844 }, isMobile: true });
} finally {
  server.close();
}
