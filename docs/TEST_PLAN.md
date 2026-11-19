# Testplan Phase 1

## Pflichtprüfungen

- Python-Kernmodelle: IDs, aware timestamps, Zustandsachsen
- Alarm-Lifecycle: doppelte aktive Ursache, Auflösung, Wiederherstellung
- SQLite: Erstellung, Foreign Keys, Unique-Index, Migration, Rollback, höheres Schema
- Repository: blockierende Operationen nur über `asyncio.to_thread`
- Adapter/Router/Permissions: Vertragsform, Dedup, deny-by-default
- Config-/Options-Flow: deutsches Formular, genau ein Entry, sichere Optionen
- Integration Setup/Unload: nur eigener Runtime-Bereich, keine Versand-Services
- Manifest/HACS/Translations: JSON und Struktur
- Ruff, Compileall, Secret-/Private-Reference-Scan

## Produktionsgrenzen

Nicht Teil der Phase-1-Tests: Installation auf VM 104, HAOS-Neustart, echte Serviceaufrufe, Pushs, Telefonie, externe Kanal-Authentifizierung, öffentliche Veröffentlichung.

