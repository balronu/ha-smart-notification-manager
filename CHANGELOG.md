# Changelog

## Unveröffentlicht – Phase 3 in Entwicklung

- Empfänger mit mehreren Geräten, Primärgerät, Verfügbarkeit und Gruppenmitgliedschaften.
- Deterministische Auflösung überlappender Gruppen und Routing-Vorschau nach Kanal-Fähigkeiten.
- Sichere deutsche Vorlagen mit erlaubten Platzhaltern und kontrolliertem Umgang mit fehlenden Werten.
- Persistente Phase-3-WebSocket-Verträge und simulationsbasierte Adapter ohne Netzwerkaktion.
- Responsive Empfänger-/Kanalverwaltung als isolierte Desktop-/Mobile-Fixture.
- Persistente Delivery-Jobs mit Idempotenz, Lease-Claims, Backoff und generischem HA-Service-Adapter; kein automatischer Echtversand.

## Unveröffentlicht – Phase 2 abgeschlossen

- Validierte Regeldefinitionen mit Prioritäten, Triggern und rekursivem Bedingungsbaum.
- Deterministische Auswertung für Zustände, Zahlen, Anwesenheit, Wochentage und Zeitfenster.
- Versionierter Regel-Store mit Duplikation, Soft-Delete und serverseitigem Editor-Berechtigungskontext.
- Read-only-Katalog aus Home-Assistant-Entity-, Device- und Area-Registry.
- Deutscher, responsiver visueller Web-Editor mit Suche, Entitätsauswahl, Vorschau und Validierung.
- Isolierte Desktop-/Mobil-Fixtures und echte PNG-Screenshots.
- Authentifiziertes HA-Panel mit Admin-geschützten WebSocket-Befehlen für
  Auflisten, Speichern, Duplizieren und Soft-Delete von Regeln.
- Optimistische Regelversionierung mit Konfliktschutz sowie serverseitiger
  Ablehnung von NaN/Infinity, ungültigen Wertebereichen, Zeitfenstern und
  Wochentagen.
- Zustands- und Anwesenheitsauswertung korrigiert: identische Zustände erzeugen
  keinen neuen Trigger, unbekannte Anwesenheit wird nicht als Abwesenheit
  gewertet.
- WebSocket-Fehler werden kontrolliert und ohne interne Stacktraces an das
  Frontend gemeldet; konkurrierende Regeländerungen sind getestet.

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

Phase 1 und Phase 2 sind in `main` integriert. Noch nicht veröffentlicht, kein Tag und kein HACS-Release. Phase 3 wurde nicht begonnen.
