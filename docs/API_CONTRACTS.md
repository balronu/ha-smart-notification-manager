# API-Verträge

Phase 1 definiert noch keinen produktiven Versand- oder WebSocket-Endpunkt.

## Domain-Verträge

- `ChannelAdapter`: `capabilities`, `async_validate`, `async_send`, optionales `async_feedback`
- `DeliveryRequest`: Attempt-ID, Empfänger-ID, Titel, Nachricht und validierte Payload
- `DeliveryResult`: Status, Provider-ID und strukturierte Fehler
- `RouteDecision`: deterministische Empfängerliste und Unterdrückungsgrund
- `AlarmLifecycleEngine`: `start(rule_id, cause_key)` und `resolve(...)`
- `SQLiteRepository`: `async_run()` und `async_schema_version()`; blockierende Arbeit wird ausgelagert
- `RuleStore`: versioniertes `async_save()`, `async_get()`, `async_list()`, sichere Duplikation und Soft-Delete
- `EntitySnapshot`: schreibgeschützter Friendly Name, Entity-ID, Bereich, Domain und Zustand aus HA-Registern
- `EvaluationContext`: reproduzierbarer Zustandssnapshot für die Bedingungsauswertung

## Editor-Grenze

`frontend/smart-notification-manager.js` ist eine responsive, deutschsprachige
Web-Komponente mit Regelübersicht, Suche, Wizard-Schritten, Entitätsauswahl,
Bedingungsgruppen, Vorschau und Validierung. Sie nimmt keine technische
JSON-Regel als Benutzereingabe an.

Die Komponente ist in Phase 2 als isoliertes Frontend-Fixture und Quellvertrag
validiert. Die produktive HA-Panel-/WebSocket-Anbindung bleibt ein späteres
HA-Adapter-Gate; dadurch werden in dieser Phase keine produktiven Schreibwege
freigeschaltet.

## Berechtigungen

`can_access()` ist nur ein internes Modellprüfwerkzeug. Es ist keine
Integration in HA-Authentifizierung oder Benutzerrechte. Bis eine
authentifizierte serverseitige Bindung mit isolierten Tests vorhanden ist,
existieren keine administrativen, benutzerbezogenen oder Versand-Aktionen.

## Lifecycle

Die Integration lädt in Phase 1 nur Metadaten. Eine SQLite-Datei entsteht erst
bei einem expliziten `SQLiteRepository.async_run()` oder
`async_schema_version()`-Aufruf. Datenbankfehler werden nicht verschluckt;
der Repository-Aufruf schlägt fehl und die Transaktion wird zurückgerollt.

## Künftige HA-Grenzen

Config Entry, native Actions, WebSocket-Befehle und Entitäten werden erst nach separatem HA-Adapter-Gate ergänzt. Jeder spätere Vertrag benötigt Schema, Berechtigung, Fehlerübersetzung, Tracebarkeit und einen isolierten Fixture-Test.
