# API-Verträge

Phase 2 definiert noch keinen produktiven Versand-Endpunkt. Der Regel-Editor
verwendet jedoch einen authentifizierten Home-Assistant-WebSocket-Vertrag.

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
- `RecipientStore`: versionlose, transaktionale Empfänger-, Gruppen-, Kanal- und Vorlagenspeicherung
- `resolve_recipients()`: deterministische Gruppen-/Geräteauflösung mit Überlappungs-Deduplizierung
- `build_routing_preview()`: fähigkeitsabhängige Vorschau ohne Adapteraufruf oder Netzwerkzugriff
- `render_template()`: begrenzte, erlaubte Platzhalter; unbekannte oder ausführbare Syntax wird abgewiesen
- `DeliveryStore`/`DeliveryService`: idempotente technische Aufträge, Lease-Claims, begrenzte Backoff-Wiederholungen und sichere Statuspersistenz
- `HAServiceAdapter`: Aufruf eines bereits registrierten `domain.service`; die Capability-Konfiguration bleibt explizit und provider-neutral

Phase 3 registriert zusätzlich die Admin-WebSocket-Befehle
`smart_notification_manager/recipient/list`, `/recipient/save`, `/group/save`,
`/channel/save`, `/template/save`, `/routing/preview`, `/delivery/enqueue` und
`/delivery/list`. Das Enqueue ruft keinen Dienst auf. Reale Adapter verwenden
ausschließlich vorhandene Home-Assistant-Dienste und benötigen zusätzlich eine
explizite Versandfreigabe; ein Anbieter-Accept ist keine Zustellbestätigung.

## WebSocket-Fehlervertrag

Ungültige Regelpayloads und Versionskonflikte werden als `invalid_format` mit
der stabilen Meldung „Die Regel ist ungültig oder darf nicht geändert werden.“
zurückgegeben. Fehlende Laufzeit, SQLite-Fehler und nicht verfügbare
Persistenz werden als `unknown_error` mit „Die Regelverwaltung ist derzeit
nicht verfügbar.“ gemeldet. Interne Exception-Texte und Stacktraces bleiben im
Serverlog und werden nicht an das Frontend übertragen.

## Editor-Grenze

`frontend/smart-notification-manager.js` ist eine responsive, deutschsprachige
Web-Komponente mit Regelübersicht, Suche, Wizard-Schritten, Entitätsauswahl,
Bedingungsgruppen, Vorschau und Validierung. Sie nimmt keine technische
JSON-Regel als Benutzereingabe an.

Die Komponente wird als Home-Assistant-Panel unter `/smart_notification_manager`
registriert und ruft ausschließlich die Admin-geschützten Befehle
`smart_notification_manager/list`, `/save`, `/delete` und `/duplicate` auf.
Die statischen Dateien werden über einen registrierten Static Path geladen.
Die API schreibt nur Regeldefinitionen in die integrationsinterne SQLite-Datenbank;
sie versendet keine Benachrichtigungen und verändert keine bestehenden HA-
Automationen. Die isolierte Browser-Fixture bleibt ergänzend für reproduzierbare
Viewport- und Bedienabläufe erhalten.

## Berechtigungen

`can_access()` ist nur ein internes Modellprüfwerkzeug. Der aktuelle
WebSocket-Adapter bindet Schreib- und Lesebefehle zusätzlich mit
`@require_admin` an den authentifizierten HA-Benutzer; die Verbindung muss eine
Benutzer-ID besitzen. Eine feinere Rollen- und Benutzerrechteverwaltung ist
weiterhin offen. Unprotected administrative or user-specific actions remain
disabled.

## Lifecycle

Die Integration lädt in Phase 2 nur den Editor-Laufzeitkontext. Eine SQLite-Datei entsteht erst
bei einem expliziten `SQLiteRepository.async_run()` oder
`async_schema_version()`-Aufruf. Datenbankfehler werden nicht verschluckt;
der Repository-Aufruf schlägt fehl und die Transaktion wird zurückgerollt.

## Künftige HA-Grenzen

Native Actions, Benachrichtigungsversand und Entitäten werden erst nach
separatem Adapter-Gate ergänzt. Jeder Vertrag benötigt Schema, Berechtigung,
Fehlerübersetzung, Tracebarkeit und einen isolierten Fixture-Test.
