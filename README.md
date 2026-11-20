# Smart Notification Manager

Zentrale, nachvollziehbare Benachrichtigungsverwaltung als Home-Assistant-Custom-Integration mit deutscher Primärdokumentation.

> **Entwicklungsstatus:** Die Infrastruktur-Gates #16–#19 und #24 sind verifiziert; die fachliche Phase-12-Abnahme ist in [docs/PHASE12_ACCEPTANCE.md](docs/PHASE12_ACCEPTANCE.md) dokumentiert und die Beta bleibt wegen offener Anforderungen gesperrt.

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

HA-Notify, Mobile-App, Telegram, WhatsApp, E-Mail und TTS sind nur über
konfigurierte HA-Aktionen beziehungsweise als Adaptergrenzen vorgesehen.
FRITZ!Box-Klingeln und SIP/PBX-Sprachanrufe sind vorbereitet, aber nicht als
vollständig implementierte Kanäle abzunehmen.

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

```bash
uv sync --extra test
uv run pytest
uv run ruff check .
python -m compileall custom_components
```

Für die Entwicklungsstände existieren noch keine öffentlichen Installationsanweisungen. Es werden keine GitHub-Releases, Tags oder öffentlichen HACS-Einträge erzeugt. Vor `v1.0.0-beta.1` müssen die Qualitäts-Gates #16 (HA-Runtime-/Panel-E2E), #17 (Hassfest), #18 (HACS) und #19 (Secret-Scan) abgeschlossen sein.

## Beiträge und Fehler

Beiträge und Fehlerberichte werden über GitHub Issues und Pull Requests angenommen. Bitte keine Zugangsdaten, privaten Nachrichteninhalte oder Standortdaten in Issues einfügen.

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE). Copyright (c) 2026
Michael Dick.

## English summary

Smart Notification Manager is a German-first Home Assistant custom integration under development. Phase 6 is integrated on `main` and adds the alarm center with server-side filtering and permissions. Alarm repeat/escalation delivery remains tracked in issue #24; full HA runtime E2E, telephony and HACS publication remain gated.
