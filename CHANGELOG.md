# Changelog

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

Phase 1 ist abgeschlossen und in `main` integriert. Noch nicht veröffentlicht, kein Tag und kein HACS-Release. Phase 2 wurde nicht begonnen.
