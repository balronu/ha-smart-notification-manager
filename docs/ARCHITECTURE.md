# Architektur

## Leitlinien

Die Integration trennt Fachlogik, Persistenz, Home-Assistant-Adapter und zukünftige Kanaladapter. Phase 2 aktiviert ausschließlich den administrativ geschützten Regel-Editor; Versand und produktive Ereignisaufzeichnung bleiben deaktiviert.

```text
Home Assistant adapter
  ├─ Config/Options Flow
  ├─ runtime lifecycle
  ├─ authenticated WebSocket API
  └─ static HA panel / future entities/actions
          │
          ▼
Domain core (HA-independent)
  Rule/Condition → Alarm Lifecycle → Router → Adapter contract
          │                         │
          ├─ Permissions            └─ Audit/Statistics contracts
          ▼
Async SQLite repository / additive migrations
```

## Module

| Modul | Verantwortung | Phase 2 |
|---|---|---|
| Rule Engine | stabile Regeldefinitionen und Versionen | validiertes Regelmodell, CRUD und Soft-Delete |
| Condition Engine | Zeitfenster und später HA-Zustandsbedingungen | deterministischer Bedingungsbaum |
| Alarm Lifecycle | aktive Ursache, Bestätigung, Abschluss, Eskalation | Duplikatschutz im Speicher |
| Scheduler | geplante Aufgaben | Schema vorbereitet |
| Delivery Router | deterministische Ziele, Dedup | reine Route-Entscheidung |
| Channel Adapter | Fähigkeiten, Validierung, Versand, Feedback | Protocol definiert, kein Versand |
| Recipient Management | Geräte, Empfänger, Gruppen | Schema vorbereitet |
| Permissions | deny-by-default Rechtebasis | pure helper |
| Storage/Migration | SQLite, Foreign Keys, Versionen | Migration v1/v2 und Regelversionen |
| Statistics | Tages-/Monatswerte | Schema vorbereitet |
| Audit/Diagnostics | technische Nachvollziehbarkeit | Schema/Vertrag vorbereitet |
| Frontend API | Editor-API | Admin-geschützte HA-WebSocket-Befehle und responsive Web-Komponente |

## Sicherheitsgrenze

Phase 2 registriert keinen Versand-Service, beobachtet keine HA-Ereignisse und schreibt keine produktive HA-Datenbank. Das Panel nutzt nur authentifizierte Admin-WebSocket-Befehle für integrationsinterne Regeldefinitionen. Ein späterer Versand darf keine beliebigen Caller-Service-Namen ausführen; alle Adapter werden über validierte Zielprofile gewählt.

## Berechtigungsgrenze

`core.permissions.can_access()` bleibt eine interne, reine Deny-by-default-
Grundlage für Domänentests. Der Phase-2-WebSocket-Adapter bindet die
Regelverwaltung zusätzlich an `@require_admin` und die authentifizierte HA-
Benutzer-ID. Eine feinere Benutzer-/Rollen-Policy ist noch offen.

Weitere APIs oder Dienste müssen dieselben Grenzen, Fehlerübersetzung,
Auditierbarkeit und isolierten Adaptertests erfüllen.

## Entitätskatalog

Der Editor bezieht seine auswählbaren Entitäten über die offiziellen
`entity_registry`, `device_registry` und `area_registry`-Helfer von Home
Assistant. Friendly Name, Entity-ID, Bereich, Domain und der aktuelle Zustand
werden zu schreibgeschützten `EntitySnapshot`-Werten zusammengeführt.
Entitäten ohne Bereich bleiben sichtbar und werden mit „Kein Bereich“
angezeigt.

## Persistenz- und Lifecycle-Grenze

Die SQLite-Datenbank wird weiterhin ausschließlich durch einen expliziten
`SQLiteRepository`-Aufruf erzeugt. `async_setup()` und `async_setup_entry()`
initialisieren absichtlich keine Datenbank und aktivieren keine Aufzeichnung.
`async_unload_entry()` entfernt nur den Runtime-Eintrag; es löscht keine
Datenbank und stoppt keine fremden Ressourcen.

Migrationen laufen innerhalb einer expliziten Transaktion. Der
Schema-Versionswechsel wird erst nach erfolgreicher Migration committed;
Fehler führen zu einem Rollback und werden an den aufrufenden Setup-/Worker-
Pfad weitergegeben.
