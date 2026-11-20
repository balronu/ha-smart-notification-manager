# Gate #16 – offizieller HA-Test-Harness und authentifizierte Persistenz

## Tatsächlicher Nachweis

- **Home Assistant Core:** `2026.11.2`
- **Offizieller Harness:** `pytest-homeassistant==2026.11.2`
- **Umgebung:** temporäres, direkt gestartetes HA-Core-Testverzeichnis mit
  eigener SQLite-Datenbank; Docker/Podman waren auf dem Prüfhost nicht
  verfügbar. VM104, produktive Geräte und produktive Zugangsdaten wurden
  nicht verwendet.
- **Ergebnis Harness:** 4 Tests bestanden. Geprüft wurden Config-Entry-Setup
  und Unload, Config Flow, offizieller Auth-Fixture-Kontext sowie die
  Ablehnung eines Admin-WebSocket-Befehls für einen Read-only-Benutzer.

## Authentifizierter Lauf

1. Ein lokaler Test-Administrator wurde über den HA-Onboarding-/Config-Flow
   angelegt.
2. Die Integration wurde authentifiziert eingerichtet und als `loaded`
   bestätigt.
3. Eine Regel mit Name, Kategorie, Beschreibung, Auslöser, Entität und
   Bedingung wurde über die authentifizierte `smart_notification_manager/save`
   API gespeichert. Die Antwort enthielt die erzeugte `rule_id` und Version 1.
4. `list` nach Browser-Neuladen zeigte dieselben Werte wieder an; der
   Nachweis ist in [gate-16-rule-saved.png](screenshots/gate-16-rule-saved.png)
   archiviert.
5. HA Core wurde beendet und mit demselben temporären Konfigurationsverzeichnis
   neu gestartet. `list` lud die Regel aus SQLite erneut mit unveränderter
   `rule_id` und Version 1.
6. Die Regel wurde danach erneut authentifiziert gespeichert. Die Antwort
   enthielt die geänderten Werte und Version 3; damit ist die Änderung nach
   Neustart und die Versionsfortschreibung nachgewiesen.

Die UI-Liste nach dem erneuten Laden ist in
[gate-16-rule-reopened.png](screenshots/gate-16-rule-reopened.png) abgelegt.
Der Browser-Shadow-DOM ließ synthetische direkte `.click()`-Aufrufe in der
isolierten Chromium-Ausführung nicht zuverlässig an den Delegaten durch. Das
wurde nicht als UI-Klick-Erfolg gewertet; die Speicherung und das erneute Laden
wurden über die authentifizierte HA-WebSocket-API und die gerenderte
Admin-Oberfläche verifiziert.

## Sicherheits- und Fehlerbefunde

- Read-only-Benutzer werden vom Admin-only-WebSocket abgewiesen.
- Import, Simulation und Testregel änderten keine produktiven Systeme und
  lösten keine Nachricht, keinen Anruf und kein TTS aus.
- Der Lauf zeigte einen HA-2026.11-Thread-Safety-Fehler in der
  Rule-Switch-Synchronisierung. Der Callback wurde auf einen asynchronen
  Dispatcher-Callback umgestellt; der Harness-Regressionsfall ist grün.
- FFmpeg, TurboJPEG, libpcap und FritzBox-Discovery-Warnungen stammen aus der
  generischen isolierten HA-Umgebung und sind keine Integrationsfehler.

## HACS-Gate

Die offizielle HACS-Action konnte gegen das private Repository nicht als
bestanden ausgeführt werden. Die Action selbst meldet, dass sie private
Repositories nur validieren kann, wenn sie öffentlich sind. Das Repository
blieb deshalb privat; lokale Struktur-/Manifestprüfungen werden nicht als
offizielle HACS-Abnahme gezählt. Gate #18 bleibt offen.
