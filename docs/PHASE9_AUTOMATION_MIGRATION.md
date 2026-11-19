# Phase 9 – Sicherer Migrationsassistent für bestehende Automationen

Phase 9 analysiert YAML-förmige Home-Assistant-Automationen ausschließlich
lesend. Die Quelle bleibt unverändert und aktiv. Die Oberfläche ist deutsch,
touchfreundlich und für schmale Ansichten geeignet.

Fixture-Nachweise: [Desktop](screenshots/phase-9-automation-desktop.png),
[iPad](screenshots/phase-9-automation-ipad.png) und
[iPhone](screenshots/phase-9-automation-iphone.png).

## Erkennung und Einstufung

Erkannt werden `notify.*`, `notify.send_message`,
`persistent_notification.create`, Mobile-App-/Telegram-Kanäle und `tts.*`.
Die Analyse läuft rekursiv durch `choose`, `if`, `repeat`, `parallel` und
verschachtelte Sequenzen. Dynamische oder unbekannte Dienste werden niemals als
sicher migrierbar eingestuft. Sicherheits-, Heizungs-, Tür-, Alarm- und
Stromautomationen benötigen ausdrücklich eine manuelle Freigabe.

Die Einstufungen sind:

1. **Vollständig migrierbar** – einfache, bekannte Benachrichtigungsautomation;
   nur ein deaktivierter Beobachtungsentwurf wird erzeugt.
2. **Hybrid migrierbar** – die ursprüngliche Logik bleibt erhalten; nur
   ausgewählte Benachrichtigungsaktionen werden für eine Vorschau durch
   `smart_notification_manager.send` ersetzt.
3. **Nur manuell migrierbar** – dynamische Dienste, nicht unterstützte Trigger
   oder Sicherheitsquellen.
4. **Nicht unterstützt** – keine erkannte Benachrichtigungsaktion.

## Vorschau, Beobachtung und Rücknahme

Vorbereitung speichert einen Hash und einen redigierten Snapshot in Schema 9.
Sie verändert keine HA-Automation, erzeugt keinen Alarm und startet keinen
Versand. Der Entwurf ist deaktiviert und der Beobachtungsmodus ist Standard.
Vor einer ausdrücklichen zweistufigen Bestätigung wird keine Aktivierung
akzeptiert. Bei der Bestätigung wird der Quell-Hash erneut geprüft; eine
zwischenzeitliche Änderung führt zum sicheren Abbruch. Aktivierung und
Rollback schreiben in Phase 9 nur den lokalen Planstatus; eine produktive
Automation wird ausschließlich in einer isolierten Fixture geprüft.

## Externe Alarmreferenzen

`automation_id` plus `execution_ref` bilden den stabilen, eindeutigen Schlüssel.
Ein wiederholtes Öffnen liefert dieselbe Manager-Alarm-ID. Update, Quittierung
und Entwarnung ändern ausschließlich die zugeordnete Referenz; eine unbekannte
Ausführungsreferenz darf keinen fremden Alarm schließen. Secrets werden aus
Vorschauen, Snapshots und Auditdaten redigiert.

## Bewusste Grenzen

Die Phase liest keine produktive Automation-Konfiguration automatisch aus VM104
und führt keine Schreiboperation am HA-Automationsspeicher aus. Eine
authentifizierte HA-Runtime-/Panel-E2E-Prüfung bleibt Gate #16. Hassfest,
HACS, Secret-Scan und automatische Wiederholungs-/Eskalationszustellung
bleiben die verbindlichen Beta-Gates #17–#19 und #24.
