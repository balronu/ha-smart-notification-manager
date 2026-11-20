# Smart Notification Manager

Zentrale, nachvollziehbare Benachrichtigungsverwaltung als Home-Assistant-Custom-Integration mit deutscher Primärdokumentation.

> **Beta-Teststand `v0.1.0-beta.4`:** Dieser manuell installierbare öffentliche Teststand behebt den verbliebenen Fokusverlust durch verspätete Panel-Ladeantworten nach dem Öffnen eines neuen Entwurfs. Er ist keine vollständige Produktabnahme; die authentifizierte HA-Browser-E2E und manuelle Praxisergebnisse stehen noch aus.

## Ziel

Der Smart Notification Manager soll Regeln, Alarmlebenszyklen, Empfänger, Kanäle, Eskalationen, Ruhezeiten, Simulation, Historie und eine responsive Oberfläche zentral verwalten. Die fachliche Zielplanung ist in [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) erfasst; unbestätigte Anforderungen sind ausdrücklich markiert.

## Phase-1-Inhalt

- Domain `smart_notification_manager` und Config-/Options-Flow
- Home-Assistant-unabhängige Kernmodelle und Schnittstellen
- Versionierte SQLite-Schema-Migration mit Foreign Keys, Indizes und eindeutiger aktiver Alarmursache
- Async-sicherer Repository-Rahmen über `asyncio.to_thread`
- Adapter-, Router-, Rechte-, Bedingungs- und Lifecycle-Verträge
- Offline-Tests ohne produktive Home-Assistant-Installation; Phase-1-Abnahme mit 17 Tests und grüner GitHub-CI

Die Datenbank wird nicht automatisch in einer produktiven HA-Instanz angelegt. Das Phase-2-Panel verwaltet nur integrationsinterne Regeldefinitionen; ein Versand-Service existiert noch nicht.

## Dokumentation

- [Architektur](docs/ARCHITECTURE.md)
- [Datenmodell](docs/DATA_MODEL.md)
- [API-Verträge](docs/API_CONTRACTS.md)
- [Anforderungen](docs/REQUIREMENTS.md)
- [Entwicklungsplan](docs/DEVELOPMENT_PLAN.md)
- [Testplan](docs/TEST_PLAN.md)
- [Release-Policy](docs/RELEASE_POLICY.md)
- [Phase 5 – Benachrichtigungspolitiken](docs/PHASE5_NOTIFICATION_POLICIES.md)
- [Phase 6 – Alarmzentrale](docs/PHASE6_ALARM_CENTER.md)
- [Phase 7 – Lovelace-Alarmkarte](docs/PHASE7_LOVELACE_CARD.md)
- [Phase 8 – Vorlagen, Assistent und Simulation](docs/PHASE8_RULE_WIZARD_TEMPLATES.md)
- [Phase 9 – Sicherer Automationsassistent](docs/PHASE9_AUTOMATION_MIGRATION.md)
- [Phase 10 – Beobachtungskarte und Simulation](docs/PHASE10_OBSERVATION_CARD.md)
- [Phase 11 – Geführte Migration und Wiederherstellung](docs/PHASE11_GUIDED_MIGRATION.md)
- [Beta-Gates und Abnahmestatus](docs/BETA_GATES.md)
- [Lizenz- und Komponentenprüfung](docs/LICENSING.md)
- [Phase 12 – Abnahmebericht](docs/PHASE12_ACCEPTANCE.md)

## Phase-2-Ergebnis

Der visuelle Regeleditor unterstützt Regelübersicht, Suche, Prioritäten,
Entitätsauswahl aus HA-Registern, Zustandsauslöser, verschachtelte
Bedingungsgruppen, verständliche Vorschau und responsive Darstellung.

![Desktop-Regel-Editor](docs/screenshots/phase-2-rule-editor-desktop.png)
![Mobile-Regel-Editor](docs/screenshots/phase-2-rule-editor-mobile.png)

Die Screenshots stammen aus dem isolierten Browser-Fixture und zeigen keine
produktive Home-Assistant-Instanz.

## Phase-3-Ergebnis

Implementiert sind die persistente grafische Verwaltung von Empfängern,
Gruppen, Kanälen, Kanalgruppen und Vorlagen, Primär-/Alle-Geräte-Auflösung,
Deduplizierung, Routing pro Regel, Versandvorschau und Versandstatus über
authentifizierte WebSocket-Verträge. Echte Nachrichten, Anrufe und TTS-
Ausgaben bleiben gesperrt.

HA-Notify, Mobile-App, E-Mail und TTS werden über konfigurierte HA-Aktionen
beziehungsweise Adaptergrenzen geführt. Telegram, WhatsApp und Telefonie
(einschließlich FRITZ!Box/SIP/PBX) sind optionale Erweiterungen. Fehlen die
entsprechenden HA-Dienste, zeigen UI und Delivery-Schicht „Nicht eingerichtet“
oder „Nicht verfügbar“; der Kernbetrieb wird dadurch nicht blockiert.

Der technische Versand-Lifecycle mit Idempotenz, Lease-Schutz und begrenztem
Backoff ist vorbereitet. Reale HA-Service-Adapter verwenden ausschließlich
konfigurierte Home-Assistant-Dienste und benötigen eine explizite Freigabe;
automatischer Echtversand ist in dieser Entwicklungsphase gesperrt.

## Phase-4-Ergebnis

Der persistente Alarm-Lifecycle unterstützt unabhängige Alarmvorgänge je
auslösender Entity, Pending/Active/Resolved/Suppressed/Overdue/Manually-Closed,
Quittierung mit Critical-Bestätigung, Entwarnung, Wiederholungszähler,
Eskalationsstufen und chronologische Ereignisse. Die Alarmverwaltung ist über
geschützte WebSocket-Kommandos und eine responsive deutsche Oberfläche
erreichbar. Eine vollständige HA-Runtime-/Panel-E2E-Prüfung sowie echte
Versandaktionen sind weiterhin nicht freigegeben.

## Phase-5-Ergebnis

Die Policy-Schicht speichert Ruhezeiten mit Zeitzonen, zeitlich begrenzte
Pausen, persistente Rate-Limits, Regelabhängigkeiten und Beobachtungsmodus.
Entscheidungen werden vor Delivery nachvollziehbar protokolliert; der
Beobachtungsmodus erzeugt keinen Versand. Reguläre Delivery-Aufträge sind
transaktional an die Policy-Prüfung gebunden. Wiederholungs- und
Eskalationsereignisse werden im Alarm-Lifecycle verwaltet, erzeugen aber noch
keine regulären Delivery-Aufträge; dies ist in [Issue #24](https://github.com/balronu/ha-smart-notification-manager/issues/24)
als verbindlicher Beta-Vorbehalt dokumentiert.

## Entwicklung

### Phase 8 – abgeschlossen

Die Phase ergänzt 14 entity-agnostische Regelvorlagen, einen deutschen
zehnstufigen Assistenten, sichere JSON-Import-/Export-Vorschauen,
serverseitige Simulation ohne Zustellung sowie Versionsvergleich und
Wiederherstellung als neue Regelversion. Die vollständige HA-Runtime-/Panel-
E2E bleibt Beta-Gate #16; reale Testversandaktionen sind nicht aktiviert.

### Phase 7 – abgeschlossen

Die integrierte Karte `custom:smart-notification-manager-card` bietet die
Ansichten Kompakt, Liste und Detail, unabhängige Filter pro Karteninstanz,
deutsche Editorfelder, WebSocket-only-Datenzugriff und serverseitig geschützte
Quittierung. Native Sensoren, Binärsensoren und Rule-Switches nutzen die
bestehende Alarm- und RuleStore-Datenkette.

### Installation über HACS

1. In HACS **Benutzerdefinierte Repositories** öffnen.
2. `balronu/ha-smart-notification-manager` als Repository vom Typ
   **Integration** hinzufügen.
3. Die Vorabversion `v0.1.0-beta.4` auswählen und installieren.
4. Home Assistant nach den üblichen eigenen Installationsschritten neu laden
   und die Integration über **Einstellungen → Geräte & Dienste** einrichten.

Diese Beta enthält keine echten Provider-Zugangsdaten und sendet durch die
Tests keine Nachrichten, Anrufe oder TTS-Ausgaben. Die authentifizierte
Browser-Abnahme ist noch offen; Feedback und Fehler bitte über
[GitHub Issues](https://github.com/balronu/ha-smart-notification-manager/issues)
melden.

## Beiträge und Fehler

Beiträge und Fehlerberichte werden über GitHub Issues und Pull Requests angenommen. Bitte keine Zugangsdaten, privaten Nachrichteninhalte oder Standortdaten in Issues einfügen.

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE). Copyright (c) 2026
Michael Dick.

## English summary

Smart Notification Manager is a German-first Home Assistant custom integration.
`v0.1.0-beta.4` is a manually installable public test release. It fixes
dropdown selection loss during background panel updates.
Telegram,
WhatsApp and telephony are optional; missing services do not block core setup.
Authenticated HA browser E2E and manual practical results remain open, so this
beta is not a complete product acceptance.
