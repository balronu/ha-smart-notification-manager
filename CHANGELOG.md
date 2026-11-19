# Changelog

## Unveröffentlicht – Phase 4 in Entwicklung

- Persistenter Alarm-Lifecycle mit eigener Alarm-ID pro auslösender Entity.
- Pending-, Aktiv-, Entwarnungs-, Unterdrückungs-, Überfälligkeits- und manueller Abschlussstatus.
- Quittierung, Sammelquittierung über API-Verträge, Critical-Bestätigung und Ereignishistorie.
- Persistente Wiederholungs- und Eskalationsstufen ohne echte Versandaktion.
- Responsive Alarmverwaltung mit Quittieren, Entwarnen, manuellem Abschluss und Ereignisansicht.
- Schema-v4-Migration; Phase-3-Delivery-Retries bleiben technisch getrennt.
- Schema-v5-Migration mit gepinnter Regelversion sowie persistenter Quittierung durch alle erforderlichen Empfänger.
- Server-seitige Revalidierung von Auslösern und Bedingungen gegen aktuelle HA-Zustände; `unknown`/`unavailable` bleiben unklar.

## Unveröffentlicht – Phase 3 abgeschlossen

- Empfänger mit mehreren Geräten, Primärgerät, Verfügbarkeit und Gruppenmitgliedschaften.
- Deterministische Auflösung überlappender Gruppen und Routing-Vorschau nach Kanal-Fähigkeiten.
- Sichere deutsche Vorlagen mit erlaubten Platzhaltern und kontrolliertem Umgang mit fehlenden Werten.
- Persistente Phase-3-WebSocket-Verträge und simulationsbasierte Adapter ohne Netzwerkaktion.
- Responsive Empfänger-/Kanalverwaltung als isolierte Desktop-/Mobile-Fixture.
- Persistente Delivery-Jobs mit Idempotenz, Lease-Claims, Backoff und generischem HA-Service-Adapter; kein automatischer Echtversand.
- Authentifizierte Live-WebSocket-Anbindung für Kanalgruppen, Vorlagen, Routing und Versandstatus.
- CRUD-Roundtrips und Browser-Fixture-Nachweise für Desktop, Tablet und Smartphone.
- Vollständige HA-HTTP-/WebSocket-/Panel-E2E bleibt wegen Issue #16 offen; Issues #16–#19 bleiben verbindliche Beta-Gates.
- FRITZ!Box-Klingeln und SIP/PBX sind vorbereitet, aber nicht als vollständig implementierte Kanäle ausgewiesen.

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

Phase 1, Phase 2 und Phase 3 sind in `main` integriert. HA-Runtime-/Panel-E2E und die Qualitäts-Gates #16–#19 sind noch offen. Noch nicht veröffentlicht, kein Tag und kein HACS-Release. Phase 4 wurde nicht begonnen.
