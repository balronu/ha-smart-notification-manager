# Phase 12 – unabhängiger Browser-E2E-Runner

Der Browser-Test läuft unabhängig vom OpenClaw-Browser über `playwright-core`
und das bereits vorhandene System-Chromium. Es wird kein Browser-Binary aus
dem Internet heruntergeladen.

## Reproduzierbarer Fixture-Lauf

```bash
npm install
npm run e2e:phase12
```

Der Standardlauf prüft die isolierte Statistik-Fixture auf Desktop, iPad und
iPhone und erzeugt Screenshots und Playwright-Traces unter
`artifacts/phase12-browser/`.

## Isolierte HA-Laufzeit

Für eine echte HA-Abnahme muss eine separat gestartete, isolierte HA-Instanz
mit `PHASE12_BASE_URL` angegeben werden. Für eine bereits authentifizierte
Testinstanz kann zusätzlich `PHASE12_STORAGE_STATE` auf einen ausschließlich
für diese Instanz erzeugten Playwright-Storage-State zeigen:

```bash
PHASE12_BASE_URL=https://127.0.0.1:8123 \
PHASE12_STORAGE_STATE=/secure/test-only/storage-state.json \
npm run e2e:phase12
```

Der Runner öffnet ausschließlich die angegebene Test-URL. Er erstellt keine
öffentlichen Listener, verwendet keine VM-104-Daten und besitzt keinen
Produktiv-Login. OpenClaw-Policy, Proxy- und Browser-Sicherheitsregeln werden
nicht verändert oder umgangen.

Der aktuelle Fixture-PASS ist kein authentifizierter HA-PASS: In der laufenden
Agent-Umgebung ist lokale OpenClaw-Browser-Navigation policy-seitig blockiert
und es ist keine isolierte HA-URL mit Storage-State vorhanden. Issue #13 und
die Beta-Sperre bleiben deshalb offen, bis dieser unabhängige Lauf gegen eine
isolierte HA-Instanz erfolgreich ausgeführt wurde.
