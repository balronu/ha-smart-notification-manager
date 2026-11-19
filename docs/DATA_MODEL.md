# Datenmodell

## Phase 2 Regeldefinition

Eine Regel wird als versionierte `RuleDefinition` gespeichert und enthält:

- stabile UUID, Name, Beschreibung, Kategorie und optionalen HA-Bereich
- Priorität `Info`, `Normal`, `Warnung` oder `Critical`
- Aktivierungsstatus und Erstellungs-/Änderungszeitpunkte
- einen oder mehrere Zustands- oder numerische Auslöser
- Mindestdauer, Verzögerung, Hysterese sowie explizite `unknown`-/`unavailable`-Policies
- rekursiven Bedingungsbaum mit UND-/ODER-Gruppen

Die fachliche Definition liegt als JSON in `rule_versions`. Die Tabelle
`rules` enthält die indexierbaren Metadaten. Löschen ist ein Soft-Delete:
Alarmhistorie und Fremdschlüssel bleiben erhalten.

Die Auswertung in `core/evaluator.py` ist vollständig frontend-unabhängig und
deterministisch. Der Web-Editor erzeugt keine freie JSON-Eingabe, sondern
validierte Formulardaten und sichtbare Bedingungsknoten.

## Zustandsachsen

Ein Alarm trennt mindestens:

- `alarm_state`: active, acknowledged, resolved
- `acknowledgement_state`: unacknowledged/acknowledged
- `delivery_state`: pending, sent, failed, suppressed
- `escalation_state`: idle, running, complete
- `closure_reason`
- `technical_error`

Die aktive Eindeutigkeit liegt auf `(rule_id, cause_key)` und wird zusätzlich durch einen partiellen SQLite-Unique-Index geschützt. Damit kann dieselbe Regelursache nicht zwei aktive Alarmvorgänge erzeugen.

## Tabellen v1

`rules`, `rule_versions`, `alarm_instances`, `alarm_events`, `acknowledgements`, `recipients`, `recipient_groups`, `recipient_group_members`, `channels`, `channel_groups`, `channel_group_members`, `delivery_attempts`, `scheduled_tasks`, `message_templates`, `saved_filters`, `statistics_daily`, `statistics_monthly`, `audit_log`, `global_settings`.

Alle Fremdschlüssel werden aktiviert. JSON-Felder bleiben an Integrationsgrenzen als JSON gespeichert; Fachobjekte erhalten eigene IDs und Zeitstempel.

## Migration

Migrationen sind additiv, versioniert über `PRAGMA user_version` und laufen transaktional. Eine Datenbank mit höherer Version wird abgelehnt. SQLite-Zugriffe laufen ausschließlich im Repository-Worker und nicht direkt im HA-Event-Loop.
