# Isolierter Home-Assistant-Runtime-Test (Gate #16)

Der nachfolgende Lauf wurde gegen eine echte, authentifizierte Home-Assistant-
Core-Testinstanz ausgeführt. Die Testinstanz war ausschließlich temporär und
isoliert; VM104 und produktive Home-Assistant-Daten waren nicht beteiligt.

## Voraussetzungen

1. Einen temporären Container oder eine gleichwertige isolierte Testinstanz
   mit der im Projekt festgelegten Home-Assistant-Version bereitstellen.
2. Ein frisches, nicht produktives Konfigurationsverzeichnis und eine leere
   Testdatenbank verwenden.
3. Keine Verbindung zu VM104, produktiven Geräten, produktiven Integrationen
   oder produktiven Zugangsdaten herstellen.
4. Einen ausschließlich für den Test erzeugten Benutzer mit Administrator-
   und WebSocket-Zugriff verwenden; das Kennwort darf nicht in Repository,
   Logs, Fixtures oder Artefakten erscheinen.

## Abnahmelauf

- Integration installieren und Config Flow authentifiziert abschließen.
- Initialisierung, Schema-Migrationen, SQLite, WebSocket-API und Panel prüfen.
- Beide Lovelace-Karten und ihre Editoren authentifiziert laden.
- Rechte, Fehlerpfade und Neustart-Wiederherstellung prüfen.
- Desktop-, iPad- und iPhone-Viewport mit Screenshots, DOM-/State-Marken,
  Browserfehlern, fehlgeschlagenen Requests, WebSocket-Diagnostik und
  Home-Assistant-Log erfassen.
- Nach jedem Lauf die Testinstanz und alle temporären Zugangsdaten zerstören.

## Tatsächlich ausgeführter Lauf

- **Runtime:** Home Assistant Core `2026.11.2` im projekt-eigenen `.venv`
  (direkter Core-Prozess als gleichwertige isolierte Testinstanz; Docker,
  Podman, LXC und Incus waren auf dem Prüfhost nicht verfügbar).
- **Ressourcen vor dem Lauf:** 2 vCPU, 6 GiB RAM, 2 GiB Swap. Es wurden keine
  Ressourcen- oder Gaständerungen vorgenommen.
- **Daten:** frisches temporäres Konfigurationsverzeichnis, eigene HA- und
  Integrations-SQLite-Datenbank, keine produktiven Integrationen oder Geräte.
- **Authentifizierung:** lokaler, nur für den Test angelegter HA-Administrator;
  Kennwort und Token wurden nicht in Repository, Logs oder Screenshots abgelegt.
- **Config Flow:** Integration authentifiziert eingerichtet, Config Entry
  erfolgreich auf `loaded` geprüft; die Integrationsdatenbank meldete Schema-
  Version 11 mit 34 Tabellen.
- **WebSocket:** authentifiziert erfolgreich geprüft: `list`, Alarm-Center-
  `list` mit Frontend-Paginierung, `alarm/process_due`, Phase-9 `discover`,
  `preview` und `prepare` sowie Phase-11 `export`, bestätigter `import`,
  `backup`, `restore` und `recovery`. Die Phase-9- und Phase-11-Läufe waren
  schreibfrei bezüglich HA-Automationen und erzeugten keine Zustellung.
- **Neustart:** nach einem Runtime-Neustart wurde der Config Entry erneut als
  `loaded` gelesen; die WebSocket-Prüfungen blieben erfolgreich.
- **Panel und Frontend:** authentifizierte HA-Panel-Seite geladen. Panel,
  beide Karten, beide Editoren und die statischen Frontend-Ressourcen wurden
  im Browser-DOM registriert und geprüft.
- **Responsive Nachweise:**
  [Desktop](screenshots/gate-16-runtime-desktop.png),
  [iPad](screenshots/gate-16-runtime-ipad.png),
  [iPhone](screenshots/gate-16-runtime-iphone.png).

## Während des Laufes behobene Runtime-Fehler

- `CONFIG_SCHEMA` wurde als tatsächlich erzeugtes, domain-gebundenes Schema
  registriert; dadurch lädt der Config Entry unter HA Core 2026.11.2.
- Die Admin-Decorator-Brücke für WebSocket-Handler wartet die asynchrone
  Berechtigungsprüfung korrekt ab; dadurch entsteht kein `coroutine was never
  awaited`-Fehler.
- Das Alarm-Center akzeptiert die vom Panel verwendeten Filter-, Seiten- und
  Sortierfelder. Die entsprechende Regression ist durch einen Test abgedeckt.

## Status

Der authentifizierte Runtime-Nachweis ist erbracht. Der ergänzende offizielle
Harness- und Regel-Persistenznachweis steht in
`docs/GATE16_OFFICIAL_HARNESS.md`. Gate #16 wird erst nach Review,
erfolgreicher PR-CI und Main-CI als geschlossen dokumentiert. Gate #18 bleibt
unabhängig davon offen, solange die offizielle HACS-Validierung wegen der
privaten Repository-Sichtbarkeit nicht vollständig ausführbar ist.
