# Smart Notification Manager

Zentrale, nachvollziehbare Benachrichtigungsverwaltung als Home-Assistant-Custom-Integration mit deutscher Primärdokumentation.

> **Entwicklungsstatus:** Phase 4 von 12 abgeschlossen und in `main` integriert. Der Alarm-Lifecycle arbeitet ausschließlich mit simulierten Versandadaptern. Die authentifizierte HA-Runtime-/Panel-E2E-Prüfung sowie Qualitäts-Gates #16–#19 bleiben vorläufige Beta-Blocker.

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

## Phase-4-Zwischenstand

Der persistente Alarm-Lifecycle unterstützt unabhängige Alarmvorgänge je
auslösender Entity, Pending/Active/Resolved/Suppressed/Overdue/Manually-Closed,
Quittierung mit Critical-Bestätigung, Entwarnung, Wiederholungszähler,
Eskalationsstufen und chronologische Ereignisse. Die Alarmverwaltung ist über
geschützte WebSocket-Kommandos und eine responsive deutsche Oberfläche
erreichbar. Eine vollständige HA-Runtime-/Panel-E2E-Prüfung sowie echte
Versandaktionen sind weiterhin nicht freigegeben.

## Entwicklung

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

Die Lizenzentscheidung ist weiterhin offen und wird vor einer öffentlichen Veröffentlichung dokumentiert.

## English summary

Smart Notification Manager is a German-first Home Assistant custom integration under development. Phase 3 is integrated on `main` and adds authenticated live configuration for recipients, channels, templates, routing and delivery status. Full HA runtime E2E, telephony and HACS publication remain gated.
