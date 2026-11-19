# Architektur

## Leitlinien

Die Integration trennt Fachlogik, Persistenz, Home-Assistant-Adapter und zukünftige Kanaladapter. Phase 1 zeichnet Verträge vor, aktiviert aber weder Versand noch produktive Aufzeichnung.

```text
Home Assistant adapter
  ├─ Config/Options Flow
  ├─ runtime lifecycle
  └─ future HA entities/actions/WebSocket API
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

| Modul | Verantwortung | Phase 1 |
|---|---|---|
| Rule Engine | stabile Regeldefinitionen und Versionen | Modelle vorbereitet |
| Condition Engine | Zeitfenster und später HA-Zustandsbedingungen | reine Zeitfensterlogik |
| Alarm Lifecycle | aktive Ursache, Bestätigung, Abschluss, Eskalation | Duplikatschutz im Speicher |
| Scheduler | geplante Aufgaben | Schema vorbereitet |
| Delivery Router | deterministische Ziele, Dedup | reine Route-Entscheidung |
| Channel Adapter | Fähigkeiten, Validierung, Versand, Feedback | Protocol definiert, kein Versand |
| Recipient Management | Geräte, Empfänger, Gruppen | Schema vorbereitet |
| Permissions | deny-by-default Rechtebasis | pure helper |
| Storage/Migration | SQLite, Foreign Keys, Versionen | Migration v1 |
| Statistics | Tages-/Monatswerte | Schema vorbereitet |
| Audit/Diagnostics | technische Nachvollziehbarkeit | Schema/Vertrag vorbereitet |
| Frontend API | spätere UI-API | bewusst nicht aktiviert |

## Sicherheitsgrenze

Phase 1 registriert keinen Versand-Service, beobachtet keine HA-Ereignisse und schreibt keine produktive Datenbank. Ein späterer Versand darf keine beliebigen Caller-Service-Namen ausführen; alle Adapter werden über validierte Zielprofile gewählt.

