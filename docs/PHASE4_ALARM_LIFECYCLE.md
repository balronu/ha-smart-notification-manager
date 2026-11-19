# Phase 4 – Alarm-Lifecycle

## Zustandsmodell

| Zustand | Bedeutung | Zulässige Folgezustände |
|---|---|---|
| `pending` | Verzögerung läuft | `active`, `suppressed`, `manually_closed` |
| `active` | Ursache ist tatsächlich aktiv | `overdue`, `resolved`, `manually_closed` |
| `overdue` | maximale Alarmdauer überschritten | `resolved`, `manually_closed` |
| `resolved` | Ursache wurde für diesen Alarm entwarnt | terminal |
| `suppressed` | Auslösung wurde vor Aktivierung unterdrückt | terminal |
| `manually_closed` | Berechtigter Benutzer hat abgeschlossen | terminal |

Quittierung ist eine getrennte Achse. Sie beendet weder die physische Ursache
noch den Alarmzustand. Critical-Alarme verlangen eine explizite Bestätigung.

## Persistenz

Schema v4 speichert Alarmdaten, Zustandsänderungen, Quittierungen,
Wiederholungszähler, nächste Wiederholung, Eskalationsstufe und Abschlussdaten.
Alle Übergänge erzeugen einen Eintrag in `alarm_events`. Die partielle
Unique-Constraint verhindert mehrere offene Vorgänge für dieselbe Regel und
auslösende Entity.

## API

Die administrativ geschützten WebSocket-Kommandos sind:

- `smart_notification_manager/alarm/list`
- `smart_notification_manager/alarm/trigger`
- `smart_notification_manager/alarm/events`
- `smart_notification_manager/alarm/acknowledge`
- `smart_notification_manager/alarm/acknowledge_many`
- `smart_notification_manager/alarm/resolve`
- `smart_notification_manager/alarm/close`

Die aktuellen Tests verwenden simulierte Adapter und lösen keine Nachrichten,
Anrufe oder TTS-Ausgaben aus. Die vollständige authentifizierte HA-Runtime-
und Panel-E2E-Prüfung bleibt als Issue #16 offen; ebenso bleiben die Gates
#17–#19 vor der ersten Beta verbindlich.
