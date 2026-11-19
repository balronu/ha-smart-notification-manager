/* Read-only Phase-10 observation/simulation Lovelace card. */
(function () {
  "use strict";
  const CARD_TYPE = "smart-notification-manager-observation-card";
  const DEFAULT_CONFIG = { title: "Beobachtungsmodus", refresh_interval: 30, rule: null, rule_id: null };
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;", "'":"&#39;"}[c]));
  class ObservationCard extends HTMLElement {
    constructor() { super(); this._config = {...DEFAULT_CONFIG}; this._hass = null; this._result = null; this._error = ""; this._timer = null; this._loading = false; this.attachShadow({mode:"open"}); }
    static getConfigElement() { return document.createElement("smart-notification-manager-observation-card-editor"); }
    static getStubConfig() { return {...DEFAULT_CONFIG}; }
    getCardSize() { return 4; }
    setConfig(config) { if (!config || typeof config !== "object") throw new Error("Eine Kartenkonfiguration ist erforderlich."); this._config = {...DEFAULT_CONFIG, ...config}; this._schedule(); this._render(); }
    set hass(value) { this._hass = value; this._schedule(); this._render(); }
    disconnectedCallback() { if (this._timer) clearTimeout(this._timer); }
    _schedule() { if (this._timer) clearTimeout(this._timer); if (!this._hass?.callWS) return; this._load(); const n = Math.max(0, Number(this._config.refresh_interval) || 0); if (n) this._timer = setTimeout(() => this._schedule(), n * 1000); }
    async _load() { if (this._loading || !this._hass?.callWS || !this._config.rule) return; this._loading = true; try { this._result = await this._hass.callWS({type:"smart_notification_manager/phase10/observe", rule:this._config.rule, rule_id:this._config.rule_id || undefined}); this._error = ""; } catch (e) { this._error = e?.message || "Die Simulation konnte nicht geladen werden."; } finally { this._loading = false; this._render(); } }
    _render() { if (!this.shadowRoot) return; const r = this._result || {}; this.shadowRoot.innerHTML = `<style>${ObservationCard.styles}</style><ha-card data-action-guarantee="no-action"><header><h2>${esc(this._config.title)}</h2><span class="badge">Beobachtungsmodus</span></header><div class="notice"><strong>Simulation · Keine produktive Aktion</strong><br>Es werden keine Nachrichten, Anrufe, TTS-Ausgaben oder Alarme ausgelöst.</div>${this._error ? `<p class="error">${esc(this._error)}</p>` : `<dl><dt>Ergebnis</dt><dd>${r.would_send ? "Hypothetische Zustellung möglich" : esc(r.delivery_reason || "Noch keine Daten")}</dd><dt>Datenlage</dt><dd>${r.data_complete === false ? "Nicht sicher bestimmbar" : "Vollständig"}</dd><dt>Frühestmögliche Zustellung</dt><dd>${esc(r.earliest_delivery || "Keine")}</dd></dl>`}<button data-refresh ${this._loading ? "disabled" : ""}>Simulation erneut prüfen</button></ha-card>`; this.shadowRoot.querySelector("[data-refresh]")?.addEventListener("click", () => this._load()); }
    static get styles() { return `:host{display:block;color:var(--primary-text-color)}ha-card{padding:16px;background:var(--ha-card-background,var(--card-background-color,#fff))}header{display:flex;justify-content:space-between;gap:12px;align-items:center}h2{font-size:1.1rem;margin:0}.badge{color:var(--primary-color,#03a9f4);font-weight:600}.notice{margin:16px 0;padding:12px;border-left:4px solid var(--primary-color,#03a9f4);background:var(--secondary-background-color,#f5f5f5)}dl{display:grid;grid-template-columns:minmax(9rem,1fr) minmax(8rem,1.5fr);gap:8px;margin:16px 0}dt{color:var(--secondary-text-color)}dd{margin:0}.error{color:var(--error-color,#db4437)}button{border:0;border-radius:18px;padding:9px 14px;background:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff)}@media(max-width:600px){header{display:block}.badge{display:block;margin-top:6px}dl{display:block}dt{margin-top:10px}}`; }
  }
  class ObservationEditor extends HTMLElement { constructor(){super(); this._config={}; this.attachShadow({mode:"open"});} setConfig(c){this._config={...DEFAULT_CONFIG,...c}; this.shadowRoot.innerHTML=`<label>Titel<input value="${esc(this._config.title)}"></label><label>Aktualisierung (Sekunden)<input type="number" value="${Number(this._config.refresh_interval)||0}"></label>`;} }
  if (!customElements.get(CARD_TYPE)) customElements.define(CARD_TYPE, ObservationCard);
  if (!customElements.get(`${CARD_TYPE}-editor`)) customElements.define(`${CARD_TYPE}-editor`, ObservationEditor);
  window.customCards = window.customCards || []; if (!window.customCards.some((x) => x.type === CARD_TYPE)) window.customCards.push({type:CARD_TYPE,name:"Smart Notification Manager Beobachtung",description:"Schreibfreie Simulation ohne produktive Aktion",preview:true,configurable:true});
})();
