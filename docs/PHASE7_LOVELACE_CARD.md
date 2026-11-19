# Phase 7 – Lovelace-Alarmkarte (abgeschlossen)

Phase 7 ergänzt die eigenständige Karte `custom:smart-notification-manager-card`.
Sie liest ausschließlich über den authentifizierten Home-Assistant-WebSocket-
Befehl `smart_notification_manager/alarm_center/list`; Detaildaten kommen über
`.../alarm_center/detail`. Es gibt keine Browser-Datenbankverbindung.

## Kartenkonfiguration

```yaml
type: custom:smart-notification-manager-card
title: Offene Sicherheitsalarme
view: detail # compact, list oder detail
max_alarms: 8
open_first: true
priorities: [critical, warning]
unacknowledged_only: true
sort: newest
group_by: category
show_acknowledge: true
show_detail_actions: true
refresh_interval: 30
```

Die Karte kann mehrfach mit unabhängigen Filtern verwendet werden. Der
grafische Editor stellt Titel, Darstellung, Anzahl, offene/unquittierte Filter,
Quittierungsaktionen und Aktualisierungsintervall auf Deutsch bereit. Die
Picker-Metadaten werden über `window.customCards` registriert; die Integration
lädt die Ressource über den statischen HA-Integrationspfad.

## Rechte und Sicherheit

Die Karte blendet Quittierungsaktionen abhängig von der Konfiguration aus,
aber die verbindliche Prüfung erfolgt weiterhin serverseitig über die bereits
existierenden Alarm-WebSocket-Verträge. Critical-Quittierungen verlangen die
zusätzliche Bestätigung. Eine Quittierung stellt keine physische Entwarnung
dar. Kiosk-Ansichten benötigen keine Sidebar- oder Zurück-Navigation.

## Native Entitäten

Die Integration stellt je Config Entry stabile Unique-IDs bereit für:

- Sensoren: offene, Critical-, nicht quittierte Alarme, aktive Pausen und Zustellfehler.
- Binärsensoren: Critical vorhanden, offener Alarm vorhanden, Zustellsystem gestört.
- Regel-Switches: Aktivierung jeder vorhandenen Regel über den bestehenden RuleStore.

Die Critical-Deaktivierung ist über den Switch geschützt. Aggregierte Werte
werden über einen gemeinsamen HA-DataUpdateCoordinator gelesen; die Entitäten
greifen nicht direkt auf SQLite zu.

## Nachweis und Einschränkungen

`frontend/phase-7-lovelace-card-fixture.html` prüft Kompakt, Liste, Detail und
mehrere unabhängige Instanzen bei Desktop-/Tablet-/Smartphone-Breiten. Das ist
ein isolierter Browser-Fixture-Nachweis, keine vollständige authentifizierte
HA-Runtime-/Panel-E2E. Dieser Nachweis bleibt als Beta-Gate #16 offen.
Hassfest (#17), HACS (#18), Secret-Scan (#19) und die automatische
Wiederholungs-/Eskalationszustellung (#24) bleiben ebenfalls offen.
