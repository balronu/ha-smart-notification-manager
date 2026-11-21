# Changelog

## v0.1.0-beta.11 – Bestätigter Speichervorgang und Save-Diagnose

### Deutsch

- Behebt den nachgewiesenen Beta.10-Abbruch: Der Frontend-Save-Handler wartet jetzt auf WebSocket-Antwort und Listenaktualisierung, bevor der Editor schließt.
- Zeigt während des Speicherns einen Ladezustand, verhindert Doppelklick-Saves, meldet Fehler konkret und erhält den Draft bei Fehlern.
- Bedingungen bleiben optional; Name, Auslöser, Entitäten und Zahlenwerte werden feldbezogen validiert. Gültige Werte wie `120` und `0` bleiben zulässig.
- Ergänzt einen datenschutzfreundlichen Save-Trace mit Build-ID, Status und Fehlercodes; nicht ausgeführte Schritte bleiben „nicht bestätigt“.
- Echter isolierter HA-WebSocket-/SQLite-Roundtrip sowie Chromium Desktop/Mobile und WebKit Mobile decken Speichern und Wiederladen ab.
- Keine Änderungen an VM104, produktiven Regeln oder echten Benachrichtigungen. Issue #13 bleibt offen.

### English

- Fixes the confirmed Beta.10 save-path break: the frontend save handler now awaits the WebSocket response and list refresh before closing the editor.
- Shows a loading state, prevents double saves, reports concrete errors, and preserves the draft on failure.
- Conditions remain optional; name, trigger, entity, and numeric fields use field-specific validation. Valid values such as `120` and `0` remain accepted.
- Adds a privacy-safe save trace with build ID, statuses, and error codes; steps not executed remain “not confirmed”.
- An isolated real HA WebSocket/SQLite round trip plus Chromium Desktop/Mobile and WebKit Mobile cover save and reload.
- No changes to VM104, productive rules, or real notifications. Issue #13 remains open.

## v0.1.0-beta.10 – Speichervorgang und Cache-Artefakt

### Deutsch

- Cache-Key auf `?v=8` erhöht, damit Beta.9-Frontend-Code nicht aus dem Browsercache weiterläuft.
- Auswahlzähler aktualisiert sich unmittelbar mit Checkbox, Filterwechsel und Entitätsdaten-Updates.
- Isolierter Browser-Regressionspfad prüft Auswahl, Draft, Speichern ohne Bedingungen und erneutes Laden.
- Keine Änderungen an VM104, produktiven Regeln oder echten Benachrichtigungen.

### English

- Cache key raised to `?v=8` so the current frontend cannot be shadowed by a cached Beta.9 artifact.
- Selection count stays synchronized across checkbox changes, filter changes, and entity-data updates.
- Isolated browser regression covers selection, draft, saving without conditions, and reload.
- No changes to VM104, productive rules, or real notifications.

## v0.1.0-beta.9 – Regelvalidierung und mobile Bedienung

### Deutsch

- Regeln mit mindestens einem gültigen Auslöser können ohne zusätzliche Bedingungen gespeichert werden; leere Bedingungsgruppen sind optional.
- Mindestdauer bedeutet jetzt: Zielzustand beginnt, bleibt für die konfigurierte Zeit aktiv und löst danach einmal aus; ein Wechsel vorher bricht ab, `unknown`/`unavailable` folgen der Konfiguration.
- Die Vorschau beschreibt Entität, Bereich, Zustand, Mindestdauer sowie verschachtelte UND-/ODER-Bedingungen und behauptet keine Empfänger oder Zustellung.
- Lange Entity-IDs und Friendly Names umbrechen auf mobilen Karten; Checkboxen und Status bleiben innerhalb der Karte bedienbar.
- Bestehende Bereichsfilter, Fremdbereich-Auswahl, Navigation, Draft-Schutz, Diagnose und gespeicherte Regeln bleiben erhalten.

### English

- Rules with at least one valid trigger can be saved without additional conditions; empty condition groups are optional.
- Minimum duration now means the target state starts, remains active for the configured time, and fires once; leaving it early aborts, while `unknown`/`unavailable` follow the configured policy.
- The preview explains entity, area, state, minimum duration, and nested AND/OR conditions without claiming recipients or delivery.
- Long entity IDs and friendly names wrap on mobile cards; checkboxes and status values remain inside the card.
- Existing area filters, outside-area selections, navigation, draft protection, diagnostics, and saved rules remain intact.

## v0.1.0-beta.8 – Mobile Panel-Navigation und Draft-Schutz

### Deutsch

- Registriert das Custom Panel in der Home-Assistant-Shell statt in einem
  iframe; dadurch bleiben die native Sidebar und mobile Navigation erreichbar.
- Aktiviert die offizielle Safe-Area-Unterstützung für Notch und iPhone-
  Insets.
- Ergänzt eine dauerhaft erreichbare, kompakte „Zur Übersicht“-Navigation,
  die den konfigurierten HA-Standardbereich verwendet und bei langen
  Regeleditor-Formularen sichtbar bleibt.
- Beim Verlassen mit ungespeicherten Änderungen wird eine Bestätigung gezeigt;
  gespeicherte Regeln werden nicht verändert. Issue #13 bleibt bis zur echten
  iPhone-Companion-Abnahme offen.

### English

- Registers the custom panel in the Home Assistant shell instead of an iframe,
  keeping the native sidebar and mobile navigation available.
- Enables Home Assistant's supported safe-area handling for iPhone notches and
  insets.
- Adds a compact, permanently reachable “Back to overview” navigation using
  the configured HA default panel and remaining visible with long editor forms.
- Leaving with unsaved changes requires confirmation; saved rules are not
  modified. Issue #13 remains open until real iPhone Companion acceptance.

## v0.1.0-beta.7 – Bereichsfilter für Entitätsauswahl

### Deutsch

- Verwendet den im Regelkopf ausgewählten Home-Assistant-Bereich als
  Standardfilter für Entitätsauswahlen in Auslösern und Bedingungen.
- Nutzt die offiziellen Entity-/Device-/Area-Registry-Zuordnungen; direkte
  Entity-Area-Zuordnungen haben Vorrang vor der Device-Area.
- Bietet „Alle Bereiche“, behält bewusst abweichende Filter bei und löscht
  beim Bereichswechsel keine bereits ausgewählten Entitäten.
- Erhält Suche, Checkbox-Bedienung, Fokus-/Dropdown-/Draft-/White-Screen-Fix
  und Diagnoseansicht. Issue #13 bleibt bis zur echten iPhone-Abnahme offen.

### English

- Uses the Home Assistant area selected in the rule header as the default
  filter for entity pickers in triggers and conditions.
- Uses the official entity/device/area registry relationships; a direct entity
  area assignment takes precedence over the device area.
- Adds “All areas”, preserves deliberate filter overrides, and never removes
  already selected entities when the rule area changes.
- Preserves search, checkbox interaction, focus/dropdown/draft/white-screen
  fixes, and diagnostics. Issue #13 remains open until real iPhone acceptance.

## v0.1.0-beta.6 – Custom-Element-Initialisierung und White-Screen-Fix

### Deutsch

- Behebt den iOS-/WebKit-White-Screen: Die Panel-Build-ID wird nicht mehr im
  Custom-Element-Konstruktor gesetzt, sondern erst in `connectedCallback()`.
- Aktualisiert die Frontend-Ressource auf `smart-notification-manager.js?v=5`
  und bestätigt damit den Beta.6-Artefaktpfad.
- Ergänzt einen Artefakt-Regressionsnachweis für `document.createElement()`,
  Initial-Render, Build-ID, Fokus, Dropdowns, verspätete WebSocket-Antworten
  und wiederholte `hass`-Updates in Chromium und WebKit.
- Die unabhängige HA-Diagnose aus Beta.5 bleibt erhalten. Issue #13 bleibt bis
  zur echten HA-Abnahme auf dem betroffenen iPhone offen.

### English

- Fixes the iOS/WebKit white screen: the panel build ID is no longer assigned
  in the custom-element constructor and is set only in `connectedCallback()`.
- Updates the frontend resource to `smart-notification-manager.js?v=5` and
  verifies the Beta.6 artifact path.
- Adds an artifact regression proof for `document.createElement()`, initial
  render, build ID, focus, dropdowns, delayed WebSocket responses, and repeated
  `hass` updates in Chromium and WebKit.
- Keeps the independent HA diagnostics from Beta.5. Issue #13 remains open
  until acceptance on the affected iPhone in real HA.

## v0.1.0-beta.5 – Eigenständige iOS-Diagnose

### Deutsch

- Ergänzt die HA-authentifizierte Diagnose-URL
  `/api/smart_notification_manager/diagnostics`.
- Prüft unabhängig vom normalen Panel-Bundle die veröffentlichte
  `smart-notification-manager.js?v=4`, Custom-Element-Registrierung,
  Initialisierung, Fehlerkanäle und den HA-WebSocket-Handshake.
- Ermöglicht auf Safari und in der Home-Assistant-App das Kopieren eines
  bereinigten Berichts ohne Cookies, Tokens, Eingabewerte oder externe
  Telemetrie.
- Diese Diagnose-Beta behebt den iOS-White-Screen noch nicht. Der Bericht
  bleibt Voraussetzung für einen gezielten Fix; Issue #13 bleibt offen.

### English

- Adds the Home Assistant-authenticated standalone diagnostic URL
  `/api/smart_notification_manager/diagnostics`.
- Checks the published `smart-notification-manager.js?v=4`, custom-element
  registration, initialization, error channels, and the HA WebSocket handshake
  independently of the normal panel bundle.
- Allows Safari and the Home Assistant app to copy a redacted report without
  cookies, tokens, input values, or external telemetry.
- This diagnostic beta does not claim to fix the iOS white screen. The report
  remains the prerequisite for a targeted fix; Issue #13 remains open.

## v0.1.0-beta.4 – Panel-Lebenszyklus und Fokusverlust

### Deutsch

- Behebt den nach Beta.3 weiterhin reproduzierbaren Fokusverlust nach dem
  Öffnen eines frischen Regelentwurfs.
- Verspätete Antworten aus Panel-Ladevorgängen ersetzen den aktiven Editor
  nicht mehr; Bereichs- und Prioritätsauswahl bleiben erhalten.
- Ergänzt einen opt-in, datensparsamen Diagnosemodus mit Build-Kennung sowie
  einen echten Chromium-Lebenszyklus-Regressionstest mit verzögerten
  WebSocket-Antworten und wiederholten `hass`-Updates.

### English

- Fixes focus loss that remained reproducible after opening a fresh rule draft
  in beta.3.
- Late panel load responses no longer replace the active editor; area and
  priority selections remain stable.
- Adds an opt-in privacy-preserving diagnostic mode with a build ID and a real
  Chromium lifecycle regression test using delayed WebSocket responses and
  repeated `hass` updates.

## v0.1.0-beta.3 – Stabile Dropdown-Auswahl

### Deutsch

- Regeleditor-Dropdowns für Bereich, Priorität, Auslöser und Bedingungen bleiben bei Hintergrundaktualisierungen geöffnet und auswählbar.
- Unsaved Drafts werden nicht durch neue Paneldaten überschrieben.
- Bereichs- und Prioritätsauswahl werden sofort in den Draft synchronisiert.
- Echter Chromium-Regressionslauf für Desktop, iPad und iPhone mit Screenshots/Traces ergänzt.

### English

- Rule-editor dropdowns for area, priority, triggers, and conditions remain usable during background panel updates.
- Unsaved drafts are preserved when fresh panel data arrives.
- Area and priority selections are synchronized into the draft immediately.
- Added a real Chromium regression run for desktop, iPad, and iPhone viewports with screenshots/traces.

## v0.1.0-beta.2 – Fehlerkorrektur für HA 2026.11.2

### Deutsch

- Bereichsauflösung im Entity-Katalog auf die offizielle HA-2026.11.2-API `async_get_area()` korrigiert.
- Statistik-WebSocket akzeptiert jetzt den vom Panel gesendeten optionalen `filters`-Umschlag.
- Parallele Panel-Ladevorgänge werden zusammengeführt; fehlgeschlagene Statistikabfragen werden nicht automatisch wiederholt und bleiben sichtbar.
- Offizieller HA-Harness-Test für leere Paneldaten mit echtem Bereich und zugeordneter Entität ergänzt.
- Keine echten Nachrichten, Anrufe oder TTS-Ausgaben; optionale Provider bleiben unverändert.

### English

- Fixed entity-area lookup for the official Home Assistant 2026.11.2 registry API by using `async_get_area()`.
- The statistics WebSocket now accepts the optional `filters` envelope sent by the panel.
- Coalesced concurrent panel loads; failed statistics requests remain visible and are not retried automatically.
- Added an official HA harness regression test with an actual area and assigned entity in the empty-panel flow.
- No real messages, calls, or TTS output; optional providers are unchanged.

## v0.1.0-beta.1 – Erste öffentliche Beta

### Deutsch

- Manuell installierbarer öffentlicher Teststand für Home Assistant.
- Deutscher Regeleditor, Alarm-Center, Empfänger-/Gruppenverwaltung,
  Zustellstatus, Wiederholung/Eskalation, Tages-/Monatsstatistik sowie
  Migrationsvorschau und Wiederherstellung enthalten.
- Telegram, WhatsApp und Telefonie sind optional und blockieren die
  Einrichtung ohne vorhandene HA-Dienste nicht.
- Authentifizierte Browser-E2E, manuelle Praxisergebnisse und die externe
  FRITZ!Box-Zielinstanzprüfung sind noch offen. Keine Stable-Abnahme.

### English

- Manually installable public Home Assistant test release.
- Includes the German rule editor, alarm center, recipient/group management,
  delivery status, retry/escalation policies, daily/monthly statistics, and
  migration preview/recovery.
- Telegram, WhatsApp, and telephony are optional and missing HA services do
  not block core setup.
- Authenticated browser E2E, manual practical results, and external FRITZ!Box
  target validation remain open. This is not a stable acceptance.

## Unveröffentlicht – Phase 11 in Entwicklung

- Versionierter Import/Export, atomare Migrationssicherungen und Neustart-Wiederherstellung ohne produktive HA-Änderung.
- Geführte deutsche Migrationsaktionen mit Konfliktprüfung, Rollback- und Duplikatschutz.

## Phase 10

- Zweite responsive Lovelace-Karte für schreibfreie Simulation und Beobachtungsmodus mit expliziter Keine-Aktion-Garantie.
- Unvollständige Zustandsdaten werden sicher als „Nicht sicher bestimmbar“ angezeigt.

## Phase 9

- Read-only-Erkennung von `notify.*`, `notify.send_message`, persistenten Benachrichtigungen, Mobile-App-Kanälen, TTS sowie verschachtelten `choose`-, `if`- und `repeat`-Sequenzen.
- Deutsche Klassifizierung mit Risiken, fehlenden Entitäten, Kanälen, Positionen und begründetem Migrationsweg.
- Vollständige Entwürfe bleiben deaktiviert und im Beobachtungsmodus; Hybridpläne ersetzen nur ausgewählte Benachrichtigungsaktionen und bewahren die übrige Automation.
- Idempotente, neustartfeste externe Alarmreferenzen sowie atomare Vorbereitungs-, Konflikt-, Bestätigungs- und Rollback-Prüfung.
- Keine Änderung bestehender Automationen, keine automatische Benachrichtigung, kein Release und kein Tag; 25 isolierte Phase-9-Regressionstests.

## Unveröffentlicht – Phase 8 abgeschlossen

- 14 deutsche, entity-agnostische Regelvorlagen mit sicherem JSON-Import/Export.
- Zehnstufiger Regel-Assistent mit bestehendem RuleStore- und Routing-Vertrag.
- Server-seitige Simulation ohne Alarm-, Delivery-, Rate-Limit- oder Auditänderung.
- Versionshistorie mit optimistischer Prüfung und Restore als neue Version.
- Keine echten Nachrichten, Anrufe, TTS-Ausgaben, Releases oder Tags.
- PR #30 ist in `main` integriert; Main-CI und die verpflichtenden PR-Checks waren erfolgreich.

## Unveröffentlicht – Phase 7 abgeschlossen

- PR #28 in `main` integriert; Lovelace-Karte, deutscher Editor und native HA-Entitäten sind verfügbar.
- Dynamische Regel-Switch-Synchronisierung verarbeitet neue, geänderte und gelöschte Regeln mit Versionsschutz.
- 85 Tests und Main-CI für Merge-Commit `5be52882d75356b3a2322c7dedf7d2461a537ab1` erfolgreich.
- Authentifizierte HA-Runtime-/Panel-E2E sowie Gates #16–#19 und Issue #24 bleiben vor der Beta offen.
- Kein Release und kein Tag.

## Unveröffentlicht – Phase 7 in Entwicklung

- Eigenständige `custom:smart-notification-manager-card` mit Kompakt-, Listen- und Detailansicht.
- Authentifizierter WebSocket-Datenzugriff, deutsche Kartenkonfiguration und unabhängige Karteninstanzen.
- Native Sensoren, Binärsensoren und geschützte Rule-Switches über die bestehende Datenkette.
- Isolierte responsive Fixture-Prüfung; echte HA-Panel-/Runtime-E2E bleibt Gate #16.
- Kein Release und kein Tag.

## Unveröffentlicht – Phase 6 abgeschlossen

- Zentrale Alarmübersicht mit serverseitiger Suche, Filtern, Sortierung,
  Gruppierung und Pagination.
- Historische Alarmkategorien, persönliche Filteransichten und Timeline-
  Details in Schema-v7; bestehende Alarm-IDs bleiben erhalten.
- Rollenbasis für Administrator, Quittierungsberechtigte und Nur-Lesen.
- Responsive deutsche Panel-Komponente für Desktop, iPad und iPhone.
- HA-Runtime-/Panel-E2E sowie Gates #16–#19 bleiben offen; kein Release und
  kein Tag.
- PR #26 wurde nach `main` integriert; Main-CI für den Merge-Commit war erfolgreich.

## Unveröffentlicht – Phase 5 abgeschlossen

- Policy-Schicht für Ruhezeiten, Pausen, Rate-Limits, Regelabhängigkeiten und Beobachtungsmodus.
- Schema-v6-Migration mit persistenter Entscheidungs- und Rate-Limit-Historie.
- Admin-geschützte Policy-WebSocket-Verträge und deutsche Panel-Anzeige.
- Keine Versandaufträge oder externen HA-Serviceaufrufe aus der Policy-Auswertung.
- Reguläre Delivery-Aufträge sind transaktional an die Policy-Auswertung gebunden;
  Preview und Beobachtungsmodus verbrauchen kein Rate-Limit.
- Server-seitige Abhängigkeitsprüfung und Regressionstests für Quiet Hours,
  Critical, Pausen, Retries und direkte WebSocket-Umgehungsversuche.
- PR #23 ist in `main` integriert; kein Release und kein Tag.
- Automatische Delivery-Aufträge für Alarmwiederholungen und Eskalationen sind
  noch offen und in Issue #24 als Beta-Vorbehalt festgehalten.

## Unveröffentlicht – Phase 4 abgeschlossen

- Persistenter Alarm-Lifecycle mit eigener Alarm-ID pro auslösender Entity.
- Pending-, Aktiv-, Entwarnungs-, Unterdrückungs-, Überfälligkeits- und manueller Abschlussstatus.
- Quittierung, Sammelquittierung über API-Verträge, Critical-Bestätigung und Ereignishistorie.
- Persistente Wiederholungs- und Eskalationsstufen ohne echte Versandaktion.
- Responsive Alarmverwaltung mit Quittieren, Entwarnen, manuellem Abschluss und Ereignisansicht.
- Schema-v4-Migration; Phase-3-Delivery-Retries bleiben technisch getrennt.
- Schema-v5-Migration mit gepinnter Regelversion sowie persistenter Quittierung durch alle erforderlichen Empfänger.
- Server-seitige Revalidierung von Auslösern und Bedingungen gegen aktuelle HA-Zustände; `unknown`/`unavailable` bleiben unklar.

## Unveröffentlicht – Phase 3 abgeschlossen

- Empfänger mit mehreren Geräten, Primärgerät, Verfügbarkeit und Gruppenmitgliedschaften.
- Deterministische Auflösung überlappender Gruppen und Routing-Vorschau nach Kanal-Fähigkeiten.
- Sichere deutsche Vorlagen mit erlaubten Platzhaltern und kontrolliertem Umgang mit fehlenden Werten.
- Persistente Phase-3-WebSocket-Verträge und simulationsbasierte Adapter ohne Netzwerkaktion.
- Responsive Empfänger-/Kanalverwaltung als isolierte Desktop-/Mobile-Fixture.
- Persistente Delivery-Jobs mit Idempotenz, Lease-Claims, Backoff und generischem HA-Service-Adapter; kein automatischer Echtversand.
- Authentifizierte Live-WebSocket-Anbindung für Kanalgruppen, Vorlagen, Routing und Versandstatus.
- CRUD-Roundtrips und Browser-Fixture-Nachweise für Desktop, Tablet und Smartphone.
- Vollständige HA-HTTP-/WebSocket-/Panel-E2E bleibt wegen Issue #16 offen; Issues #16–#19 bleiben verbindliche Beta-Gates.
- FRITZ!Box-Klingeln und SIP/PBX sind vorbereitet, aber nicht als vollständig implementierte Kanäle ausgewiesen.

## Unveröffentlicht – Phase 2 abgeschlossen

- Validierte Regeldefinitionen mit Prioritäten, Triggern und rekursivem Bedingungsbaum.
- Deterministische Auswertung für Zustände, Zahlen, Anwesenheit, Wochentage und Zeitfenster.
- Versionierter Regel-Store mit Duplikation, Soft-Delete und serverseitigem Editor-Berechtigungskontext.
- Read-only-Katalog aus Home-Assistant-Entity-, Device- und Area-Registry.
- Deutscher, responsiver visueller Web-Editor mit Suche, Entitätsauswahl, Vorschau und Validierung.
- Isolierte Desktop-/Mobil-Fixtures und echte PNG-Screenshots.
- Authentifiziertes HA-Panel mit Admin-geschützten WebSocket-Befehlen für
  Auflisten, Speichern, Duplizieren und Soft-Delete von Regeln.
- Optimistische Regelversionierung mit Konfliktschutz sowie serverseitiger
  Ablehnung von NaN/Infinity, ungültigen Wertebereichen, Zeitfenstern und
  Wochentagen.
- Zustands- und Anwesenheitsauswertung korrigiert: identische Zustände erzeugen
  keinen neuen Trigger, unbekannte Anwesenheit wird nicht als Abwesenheit
  gewertet.
- WebSocket-Fehler werden kontrolliert und ohne interne Stacktraces an das
  Frontend gemeldet; konkurrierende Regeländerungen sind getestet.

## Unveröffentlicht – Phase 1 abgeschlossen

- Neues privates Repository und Domain `smart_notification_manager`.
- Home-Assistant-Grundgerüst mit deutschem Config-/Options-Flow.
- HA-unabhängige Fachmodelle für Regeln, Alarmlebenszyklus, Routing, Rechte und Kanaladapter.
- Versioniertes SQLite-Schema mit Foreign Keys, Indizes und aktiver Alarm-Deduplizierung.
- Async-sicherer Repository-Rahmen und 17 Offline-Tests.
- Atomare SQLite-Migrationen mit Rollback und Wiederaufnahme nach Fehlern.
- Isolierte Kompatibilitätsprüfung gegen Home Assistant 2026.11.2.
- Explizite pytest-asyncio-Fixture-Loop-Konfiguration ohne Warnung.
- Anforderungsmatrix, Architektur-, Datenmodell-, API-, Test-, Entwicklungs- und Release-Dokumentation.

Phase 1, Phase 2 und Phase 3 sind in `main` integriert. HA-Runtime-/Panel-E2E und die Qualitäts-Gates #16–#19 sind noch offen. Noch nicht veröffentlicht, kein Tag und kein HACS-Release. Phase 4 wurde nicht begonnen.
