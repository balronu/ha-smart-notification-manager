# Phase 6 – Alarmzentrale

Phase 6 erweitert die bestehende Alarm-Lifecycle-Datenbank um eine zentrale,
deutsche Alarmübersicht. Alarm-IDs und die vorhandene Timeline bleiben
unverändert; die Abfrage verwendet dieselbe SQLite-Repository-Instanz.

## Implementiert

- serverseitige Suche, Filter, Sortierung, Gruppierung und Pagination
- historische Kategorie-Snapshots je Alarm
- Kategorien mit Aktivierung/Deaktivierung und Audit-Eintrag
- persönliche gespeicherte Filteransichten mit Eigentümerprüfung
- Timeline-/Detailabfrage einschließlich Delivery-Versuchen
- Rollenbasis `admin`, `acknowledger` und `read_only`
- responsive Panel-Komponente für Desktop, Tablet und Smartphone

## Abnahmegrenzen

Die lokalen Tests verwenden isolierte SQLite-Repositories und simulierte
Verbindungen. Die vollständige authentifizierte HA-HTTP-/WebSocket-/Panel-
Runtime bleibt Gate #16; Hassfest (#17), HACS (#18) und Secret-Scan (#19)
sind vor `v1.0.0-beta.1` auszuführen. VM104 und externe Benachrichtigungswege
werden nicht verwendet.
