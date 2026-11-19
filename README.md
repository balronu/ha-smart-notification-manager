# Smart Notification Manager

Zentrale, nachvollziehbare Benachrichtigungsverwaltung als Home-Assistant-Custom-Integration mit deutscher Primärdokumentation.

> **Entwicklungsstatus:** Phase 2 von 12 – visueller Regeleditor in Entwicklung. Noch nicht installierbar, kein Versand, keine Telefonie, kein HACS-Release.

## Ziel

Der Smart Notification Manager soll Regeln, Alarmlebenszyklen, Empfänger, Kanäle, Eskalationen, Ruhezeiten, Simulation, Historie und eine responsive Oberfläche zentral verwalten. Die fachliche Zielplanung ist in [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) erfasst; unbestätigte Anforderungen sind ausdrücklich markiert.

## Phase-1-Inhalt

- Domain `smart_notification_manager` und Config-/Options-Flow
- Home-Assistant-unabhängige Kernmodelle und Schnittstellen
- Versionierte SQLite-Schema-Migration mit Foreign Keys, Indizes und eindeutiger aktiver Alarmursache
- Async-sicherer Repository-Rahmen über `asyncio.to_thread`
- Adapter-, Router-, Rechte-, Bedingungs- und Lifecycle-Verträge
- Offline-Tests ohne produktive Home-Assistant-Installation; Phase-1-Abnahme mit 17 Tests und grüner GitHub-CI

Die Datenbank wird in Phase 1 nicht automatisch in einer produktiven HA-Instanz angelegt. Es existiert noch kein Versand-Service.

## Dokumentation

- [Architektur](docs/ARCHITECTURE.md)
- [Datenmodell](docs/DATA_MODEL.md)
- [API-Verträge](docs/API_CONTRACTS.md)
- [Anforderungen](docs/REQUIREMENTS.md)
- [Entwicklungsplan](docs/DEVELOPMENT_PLAN.md)
- [Testplan](docs/TEST_PLAN.md)
- [Release-Policy](docs/RELEASE_POLICY.md)

## Phase-2-Vorschau

Der visuelle Regeleditor unterstützt Regelübersicht, Suche, Prioritäten,
Entitätsauswahl aus HA-Registern, Zustandsauslöser, verschachtelte
Bedingungsgruppen, verständliche Vorschau und responsive Darstellung.

![Desktop-Regel-Editor](docs/screenshots/phase-2-rule-editor-desktop.png)
![Mobile-Regel-Editor](docs/screenshots/phase-2-rule-editor-mobile.png)

Die Screenshots stammen aus dem isolierten Browser-Fixture und zeigen keine
produktive Home-Assistant-Instanz.

## Entwicklung

```bash
uv sync --extra test
uv run pytest
uv run ruff check .
python -m compileall custom_components
```

Für Phase 1 existieren keine Installationsanweisungen. Es werden keine GitHub-Releases, Tags oder öffentlichen HACS-Einträge erzeugt.

## Beiträge und Fehler

Beiträge und Fehlerberichte werden erst nach der Phase-1-Abnahme über GitHub Issues und Pull Requests angenommen. Bitte keine Zugangsdaten, privaten Nachrichteninhalte oder Standortdaten in Issues einfügen.

## Lizenz

Die Lizenzentscheidung ist in Phase 1 offen und wird vor einer öffentlichen Veröffentlichung dokumentiert.

## English summary

Smart Notification Manager is a German-first Home Assistant custom integration under development. Phase 1 is complete and contains only the offline-safe foundation: domain models, versioned SQLite schema, Config/Options Flow and tests. Delivery, telephony, frontend and HACS publication are not available yet.
