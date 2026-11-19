# API-Verträge

Phase 1 definiert noch keinen produktiven Versand- oder WebSocket-Endpunkt.

## Domain-Verträge

- `ChannelAdapter`: `capabilities`, `async_validate`, `async_send`, optionales `async_feedback`
- `DeliveryRequest`: Attempt-ID, Empfänger-ID, Titel, Nachricht und validierte Payload
- `DeliveryResult`: Status, Provider-ID und strukturierte Fehler
- `RouteDecision`: deterministische Empfängerliste und Unterdrückungsgrund
- `AlarmLifecycleEngine`: `start(rule_id, cause_key)` und `resolve(...)`
- `SQLiteRepository`: `async_run()` und `async_schema_version()`; blockierende Arbeit wird ausgelagert

## Künftige HA-Grenzen

Config Entry, native Actions, WebSocket-Befehle und Entitäten werden erst nach separatem HA-Adapter-Gate ergänzt. Jeder spätere Vertrag benötigt Schema, Berechtigung, Fehlerübersetzung, Tracebarkeit und einen isolierten Fixture-Test.

