/* Smart Notification Manager Lovelace card (German-first, WebSocket-only). */
(function () {
  "use strict";

  const CARD_TYPE = "smart-notification-manager-card";
  const DEFAULT_CONFIG = {
    title: "Alarmübersicht",
    view: "compact",
    max_alarms: 5,
    open_first: true,
    priorities: [],
    states: [],
    areas: [],
    categories: [],
    rule_ids: [],
    unacknowledged_only: false,
    sort: "newest",
    group_by: null,
    visible_fields: ["priority", "sensor", "status", "started_at"],
    show_acknowledge: true,
    show_detail_actions: true,
    refresh_interval: 30,
  };

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

  class SmartNotificationManagerCard extends HTMLElement {
    constructor() {
      super();
      this._config = { ...DEFAULT_CONFIG };
      this._hass = null;
      this._alarms = [];
      this._total = 0;
      this._groups = {};
      this._error = "";
      this._loading = false;
      this._timer = null;
      this._detail = null;
      this.attachShadow({ mode: "open" });
    }

    static getConfigElement() { return document.createElement("smart-notification-manager-card-editor"); }
    static getStubConfig() { return { ...DEFAULT_CONFIG }; }
    getCardSize() { return this._config.view === "detail" ? 5 : 3; }
    setConfig(config) {
      if (!config || typeof config !== "object") throw new Error("Eine Kartenkonfiguration ist erforderlich.");
      this._config = { ...DEFAULT_CONFIG, ...config };
      this._scheduleRefresh();
      this._render();
    }
    set hass(value) {
      this._hass = value;
      this._scheduleRefresh();
      this._render();
    }
    get hass() { return this._hass; }
    disconnectedCallback() { this._clearTimer(); }

    _clearTimer() { if (this._timer) { clearTimeout(this._timer); this._timer = null; } }
    _scheduleRefresh() {
      this._clearTimer();
      if (!this._hass || !this._config) return;
      this._load();
      const seconds = Math.max(0, Number(this._config.refresh_interval) || 0);
      if (seconds) this._timer = setTimeout(() => this._scheduleRefresh(), seconds * 1000);
    }
    async _load() {
      if (this._loading || !this._hass?.callWS) return;
      this._loading = true;
      try {
        const filters = {};
        if (this._config.priorities?.length) filters.priorities = this._config.priorities;
        if (this._config.states?.length) filters.states = this._config.states;
        if (this._config.areas?.length) filters.area_id = this._config.areas[0];
        if (this._config.categories?.length) filters.category = this._config.categories[0];
        if (this._config.rule_ids?.length) filters.rule_id = this._config.rule_ids[0];
        if (this._config.unacknowledged_only) filters.acknowledgement_state = "unacknowledged";
        if (this._config.open_first) filters.open_only = true;
        const result = await this._hass.callWS({
          type: "smart_notification_manager/alarm_center/list",
          filters, page: 1, page_size: Math.min(100, Math.max(1, Number(this._config.max_alarms) || 5)),
          sort: this._config.sort || "newest", group_by: this._config.group_by || undefined,
        });
        this._alarms = Array.isArray(result.alarms) ? result.alarms : [];
        this._total = Number(result.total) || 0;
        this._groups = result.groups || {};
        this._error = "";
      } catch (error) {
        this._error = error?.message || "Die Alarmdaten konnten nicht geladen werden.";
      } finally {
        this._loading = false;
        this._render();
      }
    }
    async _openDetail(alarmId) {
      if (!this._hass?.callWS) return;
      try { this._detail = await this._hass.callWS({ type: "smart_notification_manager/alarm_center/detail", alarm_id: alarmId }); }
      catch (error) { this._error = error?.message || "Die Alarmdetails konnten nicht geladen werden."; }
      this._render();
    }
    async _acknowledge(alarm) {
      if (!this._hass?.callWS) return;
      if (alarm.priority === "critical" && !window.confirm("Critical-Alarm wirklich quittieren?")) return;
      try {
        await this._hass.callWS({ type: "smart_notification_manager/alarm/acknowledge", request: {
          alarm_id: alarm.alarm_id, scope: "all", critical_confirmed: alarm.priority === "critical",
        }});
        await this._load();
      } catch (error) { this._error = error?.message || "Der Alarm konnte nicht quittiert werden."; this._render(); }
    }
    _render() {
      if (!this.shadowRoot || !this._config) return;
      const open = this._alarms.filter((a) => ["pending", "active", "overdue"].includes(a.alarm_state)).length;
      const critical = this._alarms.filter((a) => a.priority === "critical").length;
      const body = this._config.view === "compact" ? this._compact() : this._list(this._config.view === "detail");
      this.shadowRoot.innerHTML = `<style>${SmartNotificationManagerCard.styles}</style><ha-card>
        <div class="header"><div class="title">${esc(this._config.title)}</div><div class="counts"><span>Offen: ${open}</span><span class="critical">Critical: ${critical}</span></div></div>
        ${this._error ? `<div class="error" role="alert">${esc(this._error)}</div>` : ""}${body}${this._detail ? this._detailDialog() : ""}
      </ha-card>`;
      this.shadowRoot.querySelectorAll("[data-alarm-id]").forEach((node) => node.addEventListener("click", () => this._openDetail(node.dataset.alarmId)));
      this.shadowRoot.querySelectorAll("[data-ack-id]").forEach((node) => node.addEventListener("click", (event) => { event.stopPropagation(); const alarm = this._alarms.find((a) => a.alarm_id === node.dataset.ackId); if (alarm) this._acknowledge(alarm); }));
      this.shadowRoot.querySelector("[data-close-detail]")?.addEventListener("click", () => { this._detail = null; this._render(); });
    }
    _compact() { return `<div class="compact">${this._alarms.slice(0, this._config.max_alarms).map((a) => this._row(a, false)).join("") || `<div class="empty">Keine offenen Alarme</div>`}</div>`; }
    _list(detail) { return `<div class="list ${detail ? "detail-list" : ""}">${this._alarms.slice(0, this._config.max_alarms).map((a) => this._row(a, detail)).join("") || `<div class="empty">Keine passenden Alarme</div>`}</div>`; }
    _row(alarm, detail) {
      const label = alarm.friendly_name || alarm.entity_id || alarm.alarm_id;
      const fields = [];
      if (this._config.visible_fields.includes("priority")) fields.push(`<span class="priority p-${esc(alarm.priority)}">${esc(alarm.priority || "unbekannt")}</span>`);
      if (this._config.visible_fields.includes("sensor")) fields.push(`<span>${esc(label)}</span>`);
      if (detail && alarm.entity_id) fields.push(`<code>${esc(alarm.entity_id)}</code>`);
      if (this._config.visible_fields.includes("status")) fields.push(`<span>${esc(alarm.status_de || alarm.alarm_state)}</span>`);
      if (this._config.visible_fields.includes("started_at")) fields.push(`<time>${esc(alarm.started_at || "")}</time>`);
      const ack = this._config.show_acknowledge && !["acknowledged", "resolved"].includes(alarm.acknowledgement_state) ? `<button data-ack-id="${esc(alarm.alarm_id)}">Quittieren</button>` : "";
      return `<article class="alarm" data-alarm-id="${esc(alarm.alarm_id)}"><div class="fields">${fields.join("")}</div><div class="actions">${ack}${this._config.show_detail_actions ? `<button class="secondary">Details</button>` : ""}</div></article>`;
    }
    _detailDialog() { const alarm = this._detail?.alarm || {}; return `<div class="dialog" role="dialog" aria-label="Alarmdetails"><button class="close" data-close-detail aria-label="Schließen">×</button><h2>${esc(alarm.friendly_name || alarm.alarm_id)}</h2><p>${esc(alarm.status_de || alarm.alarm_state)} · ${esc(alarm.acknowledgement_de || "")}</p><ol>${(this._detail.events || []).map((e) => `<li><strong>${esc(e.event_type)}</strong> ${esc(e.occurred_at)}</li>`).join("")}</ol></div>`; }
    static get styles() { return `:host{display:block;color:var(--primary-text-color);--snm-border:var(--divider-color,#ddd)}ha-card{position:relative;overflow:hidden;background:var(--ha-card-background,var(--card-background-color,#fff));color:inherit}.header{display:flex;justify-content:space-between;gap:12px;padding:16px;border-bottom:1px solid var(--snm-border)}.title{font-size:1.1rem;font-weight:600}.counts{display:flex;gap:10px;font-size:.85rem}.critical{color:var(--error-color,#db4437)}.alarm{display:flex;justify-content:space-between;gap:10px;padding:12px 16px;border-bottom:1px solid var(--snm-border);cursor:pointer}.fields{display:flex;align-items:center;gap:9px;min-width:0;flex-wrap:wrap}.fields time{color:var(--secondary-text-color);font-size:.8rem}.priority{font-weight:600;text-transform:capitalize}.p-critical{color:var(--error-color,#db4437)}.p-warning{color:var(--warning-color,#f57c00)}.p-normal{color:var(--info-color,#039be5)}button{border:0;border-radius:18px;padding:8px 12px;background:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff);cursor:pointer}.secondary{background:transparent;color:var(--primary-color,#03a9f4)}.empty,.error{padding:18px}.error{color:var(--error-color,#db4437);background:var(--error-color-rgb,transparent)}.dialog{position:absolute;inset:0;background:var(--ha-card-background,var(--card-background-color,#fff));z-index:2;padding:20px}.close{float:right;font-size:1.3rem;background:transparent;color:inherit}.dialog li{padding:6px 0}@media(max-width:600px){.header{display:block}.counts{margin-top:8px}.alarm{display:block}.actions{margin-top:9px}.actions button{margin-right:6px}}`; }
  }

  class SmartNotificationManagerCardEditor extends HTMLElement {
    constructor() { super(); this._config = {}; this.attachShadow({ mode: "open" }); }
    setConfig(config) { this._config = { ...DEFAULT_CONFIG, ...config }; this._render(); }
    _render() { this.shadowRoot.innerHTML = `<style>label{display:block;margin:12px 0;font-weight:500}input,select{width:100%;box-sizing:border-box;padding:8px;background:var(--card-background-color,#fff);color:inherit;border:1px solid var(--divider-color,#aaa);border-radius:4px}fieldset{border:0;padding:0}</style><fieldset><label>Titel<input data-key="title" value="${esc(this._config.title)}"></label><label>Darstellung<select data-key="view"><option value="compact">Kompakt</option><option value="list">Liste</option><option value="detail">Detail</option></select></label><label>Maximale Anzahl<input data-key="max_alarms" type="number" min="1" max="100" value="${Number(this._config.max_alarms) || 5}"></label><label><input data-key="open_first" type="checkbox" ${this._config.open_first ? "checked" : ""}> Offene Alarme zuerst</label><label><input data-key="unacknowledged_only" type="checkbox" ${this._config.unacknowledged_only ? "checked" : ""}> Nur unquittierte Alarme</label><label><input data-key="show_acknowledge" type="checkbox" ${this._config.show_acknowledge ? "checked" : ""}> Quittierungsaktionen anzeigen</label><label>Aktualisierung (Sekunden)<input data-key="refresh_interval" type="number" min="0" value="${Number(this._config.refresh_interval) || 0}"></label></fieldset>`; this.shadowRoot.querySelector('[data-key="view"]').value = this._config.view; this.shadowRoot.querySelectorAll("[data-key]").forEach((input) => input.addEventListener("change", () => { const key = input.dataset.key; const value = input.type === "checkbox" ? input.checked : input.type === "number" ? Number(input.value) : input.value; this._config = { ...this._config, [key]: value }; this.dispatchEvent(new CustomEvent("config-changed", { bubbles: true, composed: true, detail: { config: this._config } })); })); }
  }

  if (!customElements.get(CARD_TYPE)) customElements.define(CARD_TYPE, SmartNotificationManagerCard);
  if (!customElements.get("smart-notification-manager-card-editor")) customElements.define("smart-notification-manager-card-editor", SmartNotificationManagerCardEditor);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((item) => item.type === CARD_TYPE)) window.customCards.push({ type: CARD_TYPE, name: "Smart Notification Manager", description: "Alarmübersicht über die authentifizierte Home-Assistant-WebSocket-API", preview: true, configurable: true });
})();
