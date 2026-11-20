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
3. Über den sichtbaren Admin-Panel-Regeleditor wurden Name, Beschreibung,
   Auslöser-Entität und Bedingung ausgefüllt. Playwright klickte die sichtbaren
   Buttons `Neue Regel`, `Bedingung hinzufügen` und `Regel speichern` im
   Shadow-DOM tatsächlich an. Die Regel erschien danach mit einer Backend-
   `rule_id` und Version 1 in der sichtbaren Liste.
4. Die Browser-Trace-Datei liegt in
   [gate-16-ui-save.zip](traces/gate-16-ui-save.zip); der Speichernachweis ist
   in [gate-16-ui-save-success.png](screenshots/gate-16-ui-save-success.png)
   archiviert.
5. Nach Browser-Neuladen wurde die Regel sichtbar wieder geöffnet; Name,
   Beschreibung, Auslöser und Version stimmten überein. Nachweis:
   [gate-16-ui-reopened.png](screenshots/gate-16-ui-reopened.png).
6. HA Core wurde beendet und mit demselben temporären Konfigurationsverzeichnis
   neu gestartet. Die Regel wurde anschließend über die sichtbare Oberfläche
   erneut geladen, geöffnet, geändert und mit `Regel speichern` gespeichert.
   Die Version stieg auf 2 und die Änderung war sichtbar. Nachweis:
   [gate-16-ui-postrestart-save.png](screenshots/gate-16-ui-postrestart-save.png).

Die authentifizierte UI wurde zusätzlich bei 1440×900, 1024×1366 und 390×844
gerendert. Nachweise: [Desktop](screenshots/gate-16-runtime-ui-desktop.png),
[iPad](screenshots/gate-16-runtime-ui-ipad.png) und
[iPhone](screenshots/gate-16-runtime-ui-iphone.png).

## Sicherheits- und Fehlerbefunde

- Read-only-Benutzer werden vom Admin-only-WebSocket abgewiesen.
- Import, Simulation und Testregel änderten keine produktiven Systeme und
  lösten keine Nachricht, keinen Anruf und kein TTS aus.
- Der Lauf zeigte einen HA-2026.11-Thread-Safety-Fehler in der
  Rule-Switch-Synchronisierung. Der Callback wurde auf einen asynchronen
  Dispatcher-Callback umgestellt; der Harness-Regressionsfall ist grün.
- Der authentifizierte Browserlauf zeigte zusätzlich, dass `onclick`-,
  `oninput`- und `onchange`-Properties auf der Shadow-Root im HA-Panel nicht
  zuverlässig verarbeitet wurden und rendernde Aktionen Formularwerte
  verwarfen. Die Regel-Editor-Listener wurden auf explizite Listener mit
  Cleanup umgestellt und `add-condition` synchronisiert den Formularstand vor
  dem Rendern. Ein Frontend-Regressionsassert sowie der echte Browserlauf sind
  grün.
- FFmpeg, TurboJPEG, libpcap und FritzBox-Discovery-Warnungen stammen aus der
  generischen isolierten HA-Umgebung und sind keine Integrationsfehler.

## HACS-Gate

Die offizielle HACS-Action konnte gegen das private Repository nicht als
bestanden ausgeführt werden. Die Action selbst meldet, dass sie private
Repositories nur validieren kann, wenn sie öffentlich sind. Das Repository
blieb deshalb privat; lokale Struktur-/Manifestprüfungen werden nicht als
offizielle HACS-Abnahme gezählt. Gate #18 bleibt offen.
