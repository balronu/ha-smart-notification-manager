/* Smart Notification Manager – visual German rule editor, Phase 2. */
(function () {
  "use strict";

  const PRIORITIES = {
    info: "Info",
    normal: "Normal",
    warning: "Warnung",
    critical: "Critical",
  };
  const CONDITION_LABELS = {
    entity_state: "Entitätszustand",
    numeric: "Numerischer Wert",
    presence: "Anwesenheit",
    weekday: "Wochentag",
    time_window: "Zeitfenster",
  };

  class SmartNotificationRuleEditor extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._rules = [];
      this._entities = [];
      this._query = "";
      this._selectedId = null;
      this._draft = null;
      this._error = "";
    }

    set data(value) {
      this._rules = Array.isArray(value?.rules) ? value.rules : [];
      this._entities = Array.isArray(value?.entities) ? value.entities : [];
      this._onSave = value?.onSave;
      this._onDelete = value?.onDelete;
      this._onDuplicate = value?.onDuplicate;
      this.render();
    }

    set rules(value) {
      this._rules = Array.isArray(value) ? value : [];
      this.render();
    }

    connectedCallback() {
      this.render();
    }

    render() {
      const visible = this._rules.filter((rule) => {
        const needle = this._query.trim().toLowerCase();
        return !needle || `${rule.name} ${rule.category} ${rule.area_name || ""}`.toLowerCase().includes(needle);
      });
      this.shadowRoot.innerHTML = `<style>${this.styles()}</style>
        <main aria-label="Smart Notification Manager Regelverwaltung">
          <header class="topbar">
            <div><p class="eyebrow">Smart Notification Manager</p><h1>Regeln</h1></div>
            <button class="primary" data-action="new">＋ Neue Regel</button>
          </header>
          <section class="workspace">
            <aside class="list" aria-label="Regelübersicht">
              <label class="search">⌕<input data-field="search" placeholder="Regeln suchen …" value="${this.escape(this._query)}" /></label>
              <div class="filters"><button class="filter active">Alle</button><button class="filter">Aktiv</button><button class="filter">Deaktiviert</button></div>
              <div class="rule-items">${visible.length ? visible.map((rule) => this.ruleItem(rule)).join("") : '<p class="empty">Keine Regeln gefunden.</p>'}</div>
            </aside>
            <section class="editor" aria-label="Visueller Regeleditor">${this._draft ? this.editor() : this.welcome()}</section>
          </section>
        </main>`;
      this.bind();
    }

    welcome() {
      return `<div class="welcome"><div class="welcome-icon">✓</div><h2>Benachrichtigungsregeln</h2><p>Erstelle Regeln mit sichtbaren Auslösern und Bedingungen. Die Vorschau erklärt die Regel in verständlichem Deutsch.</p><button class="primary" data-action="new">Neue Regel erstellen</button></div>`;
    }

    ruleItem(rule) {
      const selected = rule.rule_id === this._selectedId ? " selected" : "";
      return `<button class="rule-item${selected}" data-rule="${this.escape(rule.rule_id)}"><span class="status ${rule.enabled ? "on" : "off"}"></span><span class="rule-text"><strong>${this.escape(rule.name)}</strong><small>${this.escape(rule.category)} · ${this.escape(PRIORITIES[rule.priority] || rule.priority)}</small></span><span class="chevron">›</span></button>`;
    }

    editor() {
      const draft = this._draft;
      const first = draft.triggers[0] || { entity_ids: [], kind: "state", to_state: "on", minimum_duration_seconds: 0, delay_seconds: 0 };
      const selectedEntities = new Set(first.entity_ids || []);
      const selected = this._entities.filter((entity) => selectedEntities.has(entity.entity_id));
      return `<div class="editor-head"><div><p class="eyebrow">${draft.rule_id ? "Regel bearbeiten" : "Neue Regel"}</p><h2>${this.escape(draft.name || "Unbenannte Regel")}</h2></div><button class="ghost" data-action="close">Schließen</button></div>
        ${this._error ? `<div class="error" role="alert">${this.escape(this._error)}</div>` : ""}
        <div class="steps"><span class="step active"><b>1</b> Regel</span><span class="line"></span><span class="step active"><b>2</b> Auslöser</span><span class="line"></span><span class="step active"><b>3</b> Bedingungen</span></div>
        <div class="form-grid">
          <label class="field wide"><span>Name</span><input data-field="name" value="${this.escape(draft.name)}" placeholder="z. B. Gefrierwarnung" /></label>
          <label class="field"><span>Kategorie</span><input data-field="category" value="${this.escape(draft.category || "Sonstiges")}" /></label>
          <label class="field"><span>Priorität</span><select data-field="priority">${Object.entries(PRIORITIES).map(([key, label]) => `<option value="${key}" ${draft.priority === key ? "selected" : ""}>${label}</option>`).join("")}</select></label>
          <label class="field wide"><span>Beschreibung</span><textarea data-field="description" rows="2" placeholder="Was soll diese Regel erkennen?">${this.escape(draft.description || "")}</textarea></label>
        </div>
        <section class="card"><div class="section-title"><div><h3>Auslöser</h3><p>Ein Auslöser startet die Regel. Mehrere Entitäten werden gleichwertig behandelt.</p></div><span class="badge">Visuell</span></div>
          <label class="field"><span>Entitäten suchen und auswählen</span><input data-field="entity-search" placeholder="Friendly Name oder Entity-ID" /></label>
          <div class="entity-picker">${this.entityOptions(selectedEntities)}</div>
          <div class="trigger-options"><label class="field"><span>Wechsel in Zustand</span><input data-field="to-state" value="${this.escape(first.to_state || "on")}" placeholder="on, off, home …" /></label><label class="field"><span>Mindestdauer (Sekunden)</span><input type="number" min="0" data-field="minimum-duration" value="${Number(first.minimum_duration_seconds || 0)}" /></label><label class="field"><span>Verzögerung (Sekunden)</span><input type="number" min="0" data-field="delay" value="${Number(first.delay_seconds || 0)}" /></label></div>
          <p class="selection-summary">${selected.length ? `${selected.length} Entität(en) ausgewählt: ${selected.map((item) => this.escape(item.friendly_name)).join(", ")}` : "Noch keine Entität ausgewählt."}</p>
        </section>
        <section class="card"><div class="section-title"><div><h3>Bedingungen</h3><p>Alle Bedingungen müssen nachvollziehbar erfüllt sein.</p></div><button class="secondary" data-action="add-condition">＋ Bedingung</button></div><div class="condition-tree">${this.conditionEditor(draft.conditions)}</div></section>
        <section class="preview"><span class="preview-icon">◎</span><div><strong>Regelvorschau</strong><p>${this.preview(draft, selected)}</p></div></section>
        <footer class="actions"><button class="ghost" data-action="close">Abbrechen</button><span>${draft.rule_id ? '<button class="danger" data-action="delete">Löschen</button><button class="secondary" data-action="duplicate">Duplizieren</button>' : ""}</span><button class="primary" data-action="save">Regel speichern</button></footer>`;
    }

    entityOptions(selected) {
      const needle = this.shadowRoot?.querySelector('[data-field="entity-search"]')?.value?.toLowerCase() || "";
      return this._entities.filter((entity) => `${entity.friendly_name} ${entity.entity_id} ${entity.area_name || ""}`.toLowerCase().includes(needle)).map((entity) => `<label class="entity-option"><input type="checkbox" data-entity="${this.escape(entity.entity_id)}" ${selected.has(entity.entity_id) ? "checked" : ""}/><span><strong>${this.escape(entity.friendly_name)}</strong><small>${this.escape(entity.entity_id)}${entity.area_name ? ` · ${this.escape(entity.area_name)}` : " · Kein Bereich"}</small></span><em>${this.escape(entity.state || "—")}</em></label>`).join("") || '<p class="empty">Keine passenden Entitäten.</p>';
    }

    conditionEditor(condition) {
      const node = condition || { kind: "all", children: [] };
      if (node.kind === "all" || node.kind === "any") {
        return `<div class="condition-group"><div class="group-head"><select data-condition-group><option value="all" ${node.kind === "all" ? "selected" : ""}>UND – alle erfüllen</option><option value="any" ${node.kind === "any" ? "selected" : ""}>ODER – mindestens eine erfüllt</option></select></div>${(node.children || []).map((child, index) => `<div class="condition-row" data-condition-index="${index}">${this.conditionEditor(child)}<button class="icon-button" title="Bedingung entfernen" data-action="remove-condition" data-condition-index="${index}">×</button></div>`).join("") || '<p class="empty">Noch keine Bedingungen. Füge mindestens eine hinzu.</p>'}</div>`;
      }
      const value = node.value || {};
      const entityOptions = this._entities.map((entity) => `<option value="${this.escape(entity.entity_id)}" ${value.entity_id === entity.entity_id ? "selected" : ""}>${this.escape(entity.friendly_name)} (${this.escape(entity.entity_id)})</option>`).join("");
      if (node.kind === "entity_state") return `<div class="condition-leaf"><select data-condition-type><option value="entity_state" selected>Entitätszustand</option><option value="numeric">Numerischer Wert</option><option value="presence">Anwesenheit</option><option value="weekday">Wochentag</option><option value="time_window">Zeitfenster</option></select><select data-condition-entity>${entityOptions}</select><input data-condition-state value="${this.escape(value.state || "on")}" placeholder="Zustand" /></div>`;
      return `<div class="condition-leaf"><select data-condition-type>${Object.entries(CONDITION_LABELS).map(([key, label]) => `<option value="${key}" ${node.kind === key ? "selected" : ""}>${label}</option>`).join("")}</select><select data-condition-entity>${entityOptions}</select><input data-condition-state value="${this.escape(value.state || value.threshold || "")}" placeholder="Wert" /></div>`;
    }

    preview(draft, selected) {
      const entities = selected.length ? selected.map((item) => item.friendly_name).join(", ") : "eine ausgewählte Entität";
      const state = draft.triggers?.[0]?.to_state || "den Zielzustand";
      const conditionCount = draft.conditions?.children?.length || 0;
      return `Wenn ${entities} in ${state} wechseln${draft.triggers?.[0]?.minimum_duration_seconds ? ` und mindestens ${draft.triggers[0].minimum_duration_seconds} Sekunden dort bleiben` : ""}, werden ${conditionCount ? `${conditionCount} Bedingung(en)` : "die Bedingungen"} geprüft.`;
    }

    bind() {
      this.shadowRoot.querySelectorAll("[data-rule]").forEach((button) => button.addEventListener("click", () => this.open(button.dataset.rule)));
      this.shadowRoot.querySelectorAll('[data-action="new"]').forEach((button) => button.addEventListener("click", () => this.open()));
      this.shadowRoot.querySelectorAll('[data-action="close"]').forEach((button) => button.addEventListener("click", () => { this._draft = null; this._error = ""; this.render(); }));
      this.shadowRoot.querySelector('[data-field="search"]')?.addEventListener("input", (event) => { this._query = event.target.value; this.render(); });
      this.shadowRoot.querySelector('[data-field="entity-search"]')?.addEventListener("input", () => this.render());
      this.shadowRoot.querySelectorAll('[data-action="save"]').forEach((button) => button.addEventListener("click", () => this.save()));
      this.shadowRoot.querySelectorAll('[data-action="delete"]').forEach((button) => button.addEventListener("click", () => this._onDelete?.(this._draft.rule_id)));
      this.shadowRoot.querySelectorAll('[data-action="duplicate"]').forEach((button) => button.addEventListener("click", () => this._onDuplicate?.(this._draft)));
      this.shadowRoot.querySelectorAll('[data-action="add-condition"]').forEach((button) => button.addEventListener("click", () => { this._draft.conditions.children.push({ kind: "entity_state", value: { entity_id: this._entities[0]?.entity_id || "", state: "on" }, children: [] }); this.render(); }));
      this.shadowRoot.querySelectorAll('[data-action="remove-condition"]').forEach((button) => button.addEventListener("click", () => { this._draft.conditions.children.splice(Number(button.dataset.conditionIndex), 1); this.render(); }));
    }

    open(ruleId) {
      const source = this._rules.find((rule) => rule.rule_id === ruleId);
      this._selectedId = ruleId || null;
      this._draft = source ? structuredClone(source) : { rule_id: "", name: "", description: "", category: "Sonstiges", priority: "normal", enabled: true, triggers: [{ kind: "state", entity_ids: [], to_state: "on", minimum_duration_seconds: 0, delay_seconds: 0 }], conditions: { kind: "all", children: [] } };
      this._error = "";
      this.render();
    }

    save() {
      const root = this.shadowRoot;
      const selected = [...root.querySelectorAll("[data-entity]:checked")].map((input) => input.dataset.entity);
      const trigger = this._draft.triggers[0] || { kind: "state" };
      this._draft.name = root.querySelector('[data-field="name"]').value.trim();
      this._draft.category = root.querySelector('[data-field="category"]').value.trim() || "Sonstiges";
      this._draft.description = root.querySelector('[data-field="description"]').value.trim();
      this._draft.priority = root.querySelector('[data-field="priority"]').value;
      trigger.entity_ids = selected;
      trigger.to_state = root.querySelector('[data-field="to-state"]').value.trim() || null;
      trigger.minimum_duration_seconds = Number(root.querySelector('[data-field="minimum-duration"]').value || 0);
      trigger.delay_seconds = Number(root.querySelector('[data-field="delay"]').value || 0);
      this._draft.triggers = [trigger];
      if (!this._draft.name || !selected.length || trigger.minimum_duration_seconds < 0 || trigger.delay_seconds < 0) {
        this._error = "Bitte Name, mindestens eine Entität und gültige Zeitwerte angeben.";
        this.render();
        return;
      }
      this._onSave?.(this._draft);
    }

    escape(value) {
      return String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
    }

    styles() {
      return `:host{display:block;color:#17212b;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f7f9;min-height:100%;--blue:#1769aa;--border:#d9e0e7;overflow-x:hidden}*{box-sizing:border-box}main{max-width:1440px;margin:auto;min-width:0}.topbar{display:flex;align-items:center;justify-content:space-between;padding:28px 32px;background:white;border-bottom:1px solid var(--border)}h1,h2,h3,p{margin:0}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#657586;font-weight:700;margin-bottom:5px}.topbar h1{font-size:28px}.workspace{display:grid;grid-template-columns:330px minmax(0,1fr);min-height:680px;min-width:0}.list{background:#fff;border-right:1px solid var(--border);padding:20px;min-width:0}.search{display:flex;gap:8px;align-items:center;border:1px solid var(--border);border-radius:9px;padding:0 10px;color:#657586}.search input{border:0;outline:0;width:100%;padding:11px 0;font:inherit}.filters{display:flex;gap:5px;padding:18px 0 12px}.filter,.secondary,.ghost,.danger{border:1px solid var(--border);background:white;color:#415161;border-radius:7px;padding:8px 11px;font:inherit;cursor:pointer}.filter.active{background:#e7f2fb;color:var(--blue);border-color:#9fc7e4}.rule-items{display:grid;gap:4px}.rule-item{width:100%;display:flex;gap:10px;align-items:center;text-align:left;border:0;background:white;border-radius:9px;padding:12px 8px;cursor:pointer}.rule-item:hover,.rule-item.selected{background:#eef6fc}.rule-text{display:grid;gap:3px;flex:1}.rule-text small,.entity-option small{color:#708090}.status{width:9px;height:9px;border-radius:50%;background:#9caab6}.status.on{background:#27a66f}.chevron{font-size:22px;color:#81909c}.editor{padding:32px;max-width:1000px;width:100%;min-width:0;margin:auto}.editor-head{display:flex;justify-content:space-between;align-items:start;margin-bottom:22px}.editor-head h2{font-size:26px}.steps{display:flex;align-items:center;gap:10px;color:#6a7886;margin-bottom:25px}.step{display:flex;align-items:center;gap:7px;font-size:13px}.step b{display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:#d8e1e8}.step.active b{background:var(--blue);color:#fff}.line{height:1px;background:#cbd4dc;flex:0 1 55px}.form-grid,.trigger-options{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:18px}.field{display:grid;gap:6px;color:#455463;font-size:13px;font-weight:650}.field.wide{grid-column:1/-1}.field input,.field select,.field textarea,.condition-leaf input,.condition-leaf select,.group-head select{width:100%;border:1px solid #c7d1da;border-radius:7px;padding:10px;background:#fff;color:#17212b;font:inherit;font-weight:400}.card{background:#fff;border:1px solid var(--border);border-radius:12px;padding:22px;margin:18px 0;box-shadow:0 1px 2px #17212b0b}.section-title{display:flex;justify-content:space-between;gap:15px;align-items:start;margin-bottom:18px}.section-title h3{font-size:18px}.section-title p{font-size:13px;color:#687887;margin-top:5px}.badge{font-size:12px;color:#26785b;background:#e4f6ed;border-radius:12px;padding:5px 9px}.entity-picker{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;max-height:190px;overflow:auto;margin-top:10px}.entity-option{display:grid;grid-template-columns:auto 1fr auto;gap:9px;align-items:center;padding:9px;border:1px solid #e0e6eb;border-radius:7px;font-size:13px;cursor:pointer}.entity-option span{display:grid;gap:2px}.entity-option em{font-style:normal;color:#596b79;font-size:12px}.selection-summary{font-size:13px;color:#566a7a;margin-top:13px}.condition-tree{display:grid;gap:10px}.condition-group{border-left:3px solid #a8cce6;padding-left:14px;display:grid;gap:9px}.condition-row{display:flex;gap:7px;align-items:start}.condition-row .condition-group{flex:1}.condition-leaf{display:grid;grid-template-columns:1fr 1.4fr 1fr;gap:8px;flex:1}.icon-button{border:0;background:#fce9e9;color:#a22c2c;border-radius:50%;width:28px;height:28px;cursor:pointer}.preview{display:flex;gap:13px;align-items:start;background:#eaf4fb;border:1px solid #bad9ee;border-radius:10px;padding:16px;color:#234b67}.preview-icon{font-size:25px}.preview p{font-size:14px;margin-top:5px}.actions{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:20px 0}.actions span{display:flex;gap:8px}.primary{border:0;background:var(--blue);color:#fff;border-radius:7px;padding:10px 15px;font:inherit;font-weight:700;cursor:pointer}.secondary{color:var(--blue);border-color:#a9cce5}.danger{color:#a22c2c;border-color:#e7b9b9}.error{background:#fff0f0;border:1px solid #e5a9a9;color:#8f2020;padding:11px 13px;border-radius:8px;margin-bottom:16px}.welcome{text-align:center;background:#fff;border:1px solid var(--border);border-radius:14px;padding:90px 30px;width:100%;max-width:600px;margin:80px auto}.welcome-icon{display:grid;place-items:center;width:60px;height:60px;border-radius:50%;background:#e4f6ed;color:#22865e;font-size:30px;margin:0 auto 18px}.welcome p{color:#667786;line-height:1.6;margin:10px auto 22px;max-width:450px}.empty{color:#71808d;font-size:13px;padding:20px 6px}@media(max-width:800px){.workspace{grid-template-columns:1fr}.list{border-right:0;border-bottom:1px solid var(--border)}.rule-items{grid-template-columns:repeat(2,minmax(0,1fr))}.editor{padding:22px 16px}.topbar{padding:22px 16px}.entity-picker{grid-template-columns:1fr}}@media(max-width:520px){.topbar{align-items:start;gap:15px;flex-direction:column}.topbar .primary{width:100%}.rule-items,.form-grid,.trigger-options{grid-template-columns:1fr}.field.wide{grid-column:auto}.condition-leaf{grid-template-columns:1fr}.steps{gap:5px}.step{font-size:11px}.line{flex-basis:15px}.actions{align-items:stretch;flex-wrap:wrap}.actions .primary{order:3;width:100%}.actions span{margin-left:auto}}`;
    }
  }

  if (!customElements.get("smart-notification-rule-editor")) {
    customElements.define("smart-notification-rule-editor", SmartNotificationRuleEditor);
  }
})();
