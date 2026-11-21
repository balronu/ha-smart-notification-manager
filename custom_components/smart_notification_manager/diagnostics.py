"""Authenticated, dependency-free diagnostics for the mobile panel failure."""

from __future__ import annotations

from aiohttp import web
from homeassistant.helpers.http import HomeAssistantView

DIAGNOSTIC_URL = "/api/smart_notification_manager/diagnostics"
PANEL_RESOURCE = "/smart_notification_manager_static/smart-notification-manager.js?v=5"
BUILD_ID = "beta6-custom-element-lifecycle"

DIAGNOSTIC_HTML = r"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Smart Notification Manager – Diagnose</title>
  <style>
    :root { color-scheme: light dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; padding: 20px; background: #f4f6f8; color: #18222d; }
    main { max-width: 760px; margin: 0 auto; }
    section { background: Canvas; border: 1px solid #cbd5df; border-radius: 12px; padding: 18px; margin: 12px 0; }
    h1 { font-size: 1.35rem; margin: 0 0 8px; } h2 { font-size: 1rem; margin: 0 0 12px; }
    p { line-height: 1.45; } .muted { color: #5d6c79; font-size: .92rem; }
    button { min-height: 44px; border: 0; border-radius: 8px; padding: 10px 14px; margin: 4px 6px 4px 0; font: inherit; cursor: pointer; background: #1769aa; color: white; }
    button.secondary { background: #526270; } button:disabled { opacity: .55; }
    ul { list-style: none; padding: 0; margin: 0; } li { display: grid; grid-template-columns: 9rem 1fr; gap: 10px; border-top: 1px solid #dce3e9; padding: 10px 0; }
    li:first-child { border-top: 0; } .status { font-weight: 700; } .ok { color: #087443; } .error { color: #a31d28; } .unknown { color: #735d00; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: .82rem; background: #eef2f5; padding: 10px; border-radius: 8px; }
    @media (prefers-color-scheme: dark) { body { background: #111820; color: #eef3f7; } section { border-color: #394754; } .muted { color: #b5c0ca; } pre { background: #202b35; } li { border-color: #394754; } }
  </style>
</head>
<body>
<main>
  <section>
    <h1>Smart Notification Manager – Diagnose</h1>
    <p class="muted">Diese Seite benötigt die normale Home-Assistant-Anmeldung. Sie sendet keine Telemetrie und liest keine Cookies, Tokens oder Formulareingaben aus.</p>
    <button id="run">Diagnose starten</button><button id="copy" class="secondary" disabled>Bereinigten Bericht kopieren</button>
    <p id="summary" class="muted">Noch nicht gestartet.</p>
  </section>
  <section><h2>Prüfungen</h2><ul id="checks"><li><span class="status unknown">Nicht geprüft</span><span>Diagnose noch nicht gestartet.</span></li></ul></section>
  <section><h2>Umgebung</h2><pre id="environment">Wird mit der Diagnose erfasst.</pre></section>
</main>
<script>
(() => {
  "use strict";
  const BUILD_ID = "beta6-custom-element-lifecycle";
  const RESOURCE = "/smart_notification_manager_static/smart-notification-manager.js?v=5";
  const checks = new Map();
  const errors = [];
  let report = null;
  const checksNode = document.querySelector("#checks");
  const summaryNode = document.querySelector("#summary");
  const environmentNode = document.querySelector("#environment");
  const runButton = document.querySelector("#run");
  const copyButton = document.querySelector("#copy");

  const safeError = (value) => String(value?.message || value || "Unbekannter Fehler").slice(0, 240);
  window.addEventListener("error", (event) => errors.push({ type: "error", message: safeError(event.error || event.message) }));
  window.addEventListener("unhandledrejection", (event) => { errors.push({ type: "unhandledrejection", message: safeError(event.reason) }); });

  const render = () => {
    checksNode.innerHTML = [...checks].map(([name, value]) => `<li><span class="status ${value.status}">${value.status === "ok" ? "OK" : value.status === "error" ? "Fehler" : "Nicht prüfbar"}</span><span><strong>${name}</strong><br>${value.detail}</span></li>`).join("");
  };
  const setCheck = (name, status, detail) => { checks.set(name, { status, detail: String(detail).slice(0, 500) }); render(); };
  const timeout = (promise, ms, label) => Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error(label)), ms))]);
  const resourceUrl = () => new URL(RESOURCE, window.location.origin).href;

  async function checkResource() {
    const response = await timeout(fetch(resourceUrl(), { cache: "no-store" }), 5000, "Ressource-Timeout");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const text = await response.text();
    if (!text.includes(`const BUILD_ID = "${BUILD_ID}"`)) throw new Error("Build-ID im geladenen Artefakt fehlt");
    setCheck("Panel-Ressource", "ok", `${response.status} · ${new URL(response.url).pathname}?v=5 · Build ${BUILD_ID}`);
  }

  async function checkPanel() {
    const moduleUrl = `${resourceUrl()}&snm_diag=${Date.now()}`;
    await timeout(import(moduleUrl), 5000, "Panel-Import-Timeout");
    const registered = customElements.get("smart-notification-manager-panel");
    if (!registered) throw new Error("Custom Element nicht registriert");
    const panel = document.createElement("smart-notification-manager-panel");
    if (panel.hasAttribute("data-snm-build")) throw new Error("Build-ID wurde unzulässig im Konstruktor gesetzt");
    panel.hidden = true;
    document.body.append(panel);
    await new Promise((resolve) => requestAnimationFrame(resolve));
    const build = panel.dataset.snmBuild || "nicht gesetzt";
    const rendered = Boolean(panel.shadowRoot && panel.shadowRoot.childElementCount);
    const editorRendered = Boolean(panel.shadowRoot?.querySelector("smart-notification-rule-editor")?.shadowRoot?.childElementCount);
    panel.remove();
    if (!rendered || !editorRendered) throw new Error("Kein sichtbarer Initial-Render");
    if (build !== BUILD_ID) throw new Error(`Unerwartete Build-ID: ${build}`);
    setCheck("Panel-Initialisierung", "ok", `Custom Element, connectedCallback und Initial-Render · ${build}`);
  }

  async function checkWebSocket() {
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${scheme}//${window.location.host}/api/websocket`);
    await timeout(new Promise((resolve, reject) => {
      socket.addEventListener("message", (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "auth_required") { socket.close(); resolve(); }
        } catch (error) { reject(error); }
      });
      socket.addEventListener("error", () => reject(new Error("WebSocket-Verbindung fehlgeschlagen")));
    }), 5000, "WebSocket-Handshake-Timeout");
    setCheck("HA-WebSocket", "ok", "auth_required empfangen; Erreichbarkeit geprüft. Kein Zugriffstoken wurde verarbeitet.");
  }

  async function run() {
    runButton.disabled = true; copyButton.disabled = true; checks.clear(); errors.length = 0; render();
    environmentNode.textContent = JSON.stringify({ browser: navigator.userAgent, platform: navigator.platform || "unbekannt", language: navigator.language, build: BUILD_ID, resource: `${location.origin}${RESOURCE}` }, null, 2);
    const task = async (name, fn) => { try { await fn(); } catch (error) { setCheck(name, "error", safeError(error)); } };
    await task("Panel-Ressource", checkResource);
    await task("Panel-Initialisierung", checkPanel);
    await task("HA-WebSocket", checkWebSocket);
    if (errors.length) setCheck("JavaScript-Fehlerkanal", "error", errors.map((item) => `${item.type}: ${item.message}`).join(" · "));
    else setCheck("JavaScript-Fehlerkanal", "ok", "Keine unhandled errors oder Promise-Rejections während der Diagnose.");
    report = { build: BUILD_ID, resource: RESOURCE, checks: Object.fromEntries(checks), errors: errors.map((item) => ({ type: item.type, message: item.message })), environment: { userAgent: navigator.userAgent, platform: navigator.platform || "unbekannt", language: navigator.language } };
    summaryNode.textContent = [...checks.values()].some((item) => item.status === "error") ? "Diagnose abgeschlossen: mindestens eine Prüfung ist fehlgeschlagen." : "Diagnose abgeschlossen.";
    copyButton.disabled = false; runButton.disabled = false;
  }
  runButton.addEventListener("click", () => { run().catch((error) => { setCheck("Diagnose", "error", safeError(error)); runButton.disabled = false; }); });
  copyButton.addEventListener("click", async () => {
    if (!report) return;
    const text = JSON.stringify(report, null, 2);
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
      else { const area = document.createElement("textarea"); area.value = text; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0"; document.body.append(area); area.select(); document.execCommand("copy"); area.remove(); }
      copyButton.textContent = "Bericht kopiert";
    } catch (error) { copyButton.textContent = "Kopieren nicht möglich"; setCheck("Bericht kopieren", "error", safeError(error)); }
  });
})();
</script>
</body>
</html>"""


class SmartNotificationManagerDiagnosticsView(HomeAssistantView):
    """Serve diagnostics only through Home Assistant's authenticated HTTP layer."""

    url = DIAGNOSTIC_URL
    name = "api:smart_notification_manager:diagnostics"
    requires_auth = True
    cors_allowed = False

    async def get(self, request: web.Request) -> web.Response:
        """Return the standalone diagnostic document without state or secrets."""

        return web.Response(
            text=DIAGNOSTIC_HTML,
            content_type="text/html",
            headers={"Cache-Control": "no-store"},
        )
