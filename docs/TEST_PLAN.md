# Testplan Phase 1

## Pflichtprüfungen

Die Phase-1-CI nutzt den Python-3.14-Kanal und unterstützt Home Assistant
2026.10.x bis 2026.11.x. Das produktive Zielsystem ist HA 2026.11.2. Ein
isolierter Lauf gegen HA 2026.11.2 wurde ohne produktive Installation mit
dem projektunabhängigen Test-Harness ausgeführt und bestand mit 17 Tests.
Das ist eine isolierte Kompatibilitätsaussage, keine Freigabe für eine
Installation auf VM104.

- Python-Kernmodelle: IDs, aware timestamps, Zustandsachsen, Regelvalidierung
- Alarm-Lifecycle: doppelte aktive Ursache, Auflösung, Wiederherstellung
- SQLite: Erstellung, Foreign Keys, Unique-Index, atomare Migration,
  Rollback bei absichtlich fehlerhafter Migration, Wiederaufnahme, höheres Schema
- Repository: blockierende Operationen nur über `asyncio.to_thread`
- Adapter/Router/Permissions: Vertragsform, Dedup, deny-by-default, authentifizierter Editor-Kontext
- Bedingungsauswertung: verschachtelte UND-/ODER-Gruppen, numerische Vergleiche, Anwesenheit,
  Wochentage, Zeitfenster, unknown/unavailable
- Regel-Storage: Versionen, ungültige Änderungen ohne Schreibvorgang, Duplikation und Soft-Delete
- Entitätskatalog: offizielle HA-Register, bereichslose Entitäten und aktuelle Zustände
- Frontend: Syntaxvertrag, visuelle Felder, kein JSON-Editor, responsive Regeln für Desktop und Mobilbreite
- Browser-Smoke: Chromium öffnet den Editor, klickt „Bedingung“ und bestätigt das aktualisierte DOM
- Config-/Options-Flow: deutsches Formular, genau ein Entry, sichere Optionen
- Integration Setup/Unload: nur eigener Runtime-Bereich, keine
  Datenbankinitialisierung, keine Versand-Services, idempotentes Unload
- Manifest/HACS/Translations: JSON und Struktur
- Ruff, Compileall, Secret-/Private-Reference-Scan

## Produktionsgrenzen

Nicht Teil der Phase-1-Tests: Installation auf VM 104, HAOS-Neustart, echte Serviceaufrufe, Pushs, Telefonie, externe Kanal-Authentifizierung, öffentliche Veröffentlichung.
