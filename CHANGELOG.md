# Changelog

## Unveröffentlicht – Phase 9 in Entwicklung

- Read-only-Erkennung von `notify.*`, `notify.send_message`, persistenten Benachrichtigungen, Mobile-App-Kanälen, TTS sowie verschachtelten `choose`-, `if`- und `repeat`-Sequenzen.
- Deutsche Klassifizierung mit Risiken, fehlenden Entitäten, Kanälen, Positionen und begründetem Migrationsweg.
- Vollständige Entwürfe bleiben deaktiviert und im Beobachtungsmodus; Hybridpläne ersetzen nur ausgewählte Benachrichtigungsaktionen und bewahren die übrige Automation.
- Idempotente, neustartfeste externe Alarmreferenzen sowie atomare Vorbereitungs-, Konflikt-, Bestätigungs- und Rollback-Prüfung.
- Keine Änderung bestehender Automationen, keine automatische Benachrichtigung, kein Release und kein Tag; 25 isolierte Phase-9-Regressionstests.

## Unveröffentlicht – Phase 8 abgeschlossen

- 14 deutsche, entity-agnostische Regelvorlagen mit sicherem JSON-Import/Export.
- Zehnstufiger Regel-Assistent mit bestehendem RuleStore- und Routing-Vertrag.
- Server-seitige Simulation ohne Alarm-, Delivery-, Rate-Limit- oder Auditänderung.
- Versionshistorie mit optimistischer Prüfung und Restore als neue Version.
- Keine echten Nachrichten, Anrufe, TTS-Ausgaben, Releases oder Tags.
- PR #30 ist in `main` integriert; Main-CI und die verpflichtenden PR-Checks waren erfolgreich.

## Unveröffentlicht – Phase 7 abgeschlossen

- PR #28 in `main` integriert; Lovelace-Karte, deutscher Editor und native HA-Entitäten sind verfügbar.
- Dynamische Regel-Switch-Synchronisierung verarbeitet neue, geänderte und gelöschte Regeln mit Versionsschutz.
- 85 Tests und Main-CI für Merge-Commit `5be52882d75356b3a2322c7dedf7d2461a537ab1` erfolgreich.
- Authentifizierte HA-Runtime-/Panel-E2E sowie Gates #16–#19 und Issue #24 bleiben vor der Beta offen.
- Kein Release und kein Tag.

## Unveröffentlicht – Phase 7 in Entwicklung

- Eigenständige `custom:smart-notification-manager-card` mit Kompakt-, Listen- und Detailansicht.
- Authentifizierter WebSocket-Datenzugriff, deutsche Kartenkonfiguration und unabhängige Karteninstanzen.
- Native Sensoren, Binärsensoren und geschützte Rule-Switches über die bestehende Datenkette.
- Isolierte responsive Fixture-Prüfung; echte HA-Panel-/Runtime-E2E bleibt Gate #16.
- Kein Release und kein Tag.

## Unveröffentlicht – Phase 6 abgeschlossen

- Zentrale Alarmübersicht mit serverseitiger Suche, Filtern, Sortierung,
  Gruppierung und Pagination.
- Historische Alarmkategorien, persönliche Filteransichten und Timeline-
  Details in Schema-v7; bestehende Alarm-IDs bleiben erhalten.
- Rollenbasis für Administrator, Quittierungsberechtigte und Nur-Lesen.
- Responsive deutsche Panel-Komponente für Desktop, iPad und iPhone.
- HA-Runtime-/Panel-E2E sowie Gates #16–#19 bleiben offen; kein Release und
  kein Tag.
- PR #26 wurde nach `main` integriert; Main-CI für den Merge-Commit war erfolgreich.

## Unveröffentlicht – Phase 5 abgeschlossen

- Policy-Schicht für Ruhezeiten, Pausen, Rate-Limits, Regelabhängigkeiten und Beobachtungsmodus.
- Schema-v6-Migration mit persistenter Entscheidungs- und Rate-Limit-Historie.
- Admin-geschützte Policy-WebSocket-Verträge und deutsche Panel-Anzeige.
- Keine Versandaufträge oder externen HA-Serviceaufrufe aus der Policy-Auswertung.
- Reguläre Delivery-Aufträge sind transaktional an die Policy-Auswertung gebunden;
  Preview und Beobachtungsmodus verbrauchen kein Rate-Limit.
- Server-seitige Abhängigkeitsprüfung und Regressionstests für Quiet Hours,
  Critical, Pausen, Retries und direkte WebSocket-Umgehungsversuche.
- PR #23 ist in `main` integriert; kein Release und kein Tag.
- Automatische Delivery-Aufträge für Alarmwiederholungen und Eskalationen sind
  noch offen und in Issue #24 als Beta-Vorbehalt festgehalten.

## Unveröffentlicht – Phase 4 abgeschlossen

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
