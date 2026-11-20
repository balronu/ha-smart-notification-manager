# Kanal-Fähigkeitsmatrix (Phase 3)

Diese Matrix beschreibt den tatsächlich implementierten Vertrag. Ein Kanal ist
nur verfügbar, wenn der konfigurierte Home-Assistant-Dienst registriert ist.
Die Integration erfindet keine Anbieter-API und speichert keine Zugangsdaten.

| Kanal | Status | Benötigte HA-Schnittstelle | Nachgewiesene Fähigkeiten | Einschränkung |
|---|---|---|---|---|
| HA-Notify / Mobile App | implementiert | konfigurierter `notify.*`-Dienst | Nachricht, optionaler Titel, konfigurierbare Service-Daten | Fähigkeiten werden pro Kanal konfiguriert; keine Zustellgarantie |
| Telegram | über HA-Notify nutzbar | vorhandener Telegram-Notify-Dienst oder `telegram_bot.send_message`-Action | Ziel/Chat-ID wird über die konfigurierte HA-Service-Datenstruktur weitergereicht | keine direkte Telegram-API; Chat-IDs müssen in HA erlaubt sein |
| WhatsApp | vorbereitet über HA-Integration | vorhandener HA-Dienst der Integration | nur explizit konfigurierte Fähigkeiten | keine proprietäre API |
| E-Mail | über HA-Dienst nutzbar | vorhandener SMTP-Notify-Dienst bzw. `smtp.send_message`-Action | Nachricht, optionaler Titel und konfiguriertes Ziel | SMTP-Zugang und Providerzustellung nicht garantiert |
| TTS | über HA-Dienst nutzbar | vorhandener TTS-/Lautsprecher-Dienst, z. B. `tts.speak` | Nachricht, optionaler Titel und konfigurierbare Service-Daten | keine Sprachausgabe in Tests |
| FRITZ!Box-Klingeln | vorbereitet | vorhandener HA-Service | nur Klingelaktion, keine Sprache | Klingeln und TTS bleiben getrennt |
| SIP/PBX-TTS | vorbereitet | vorhandener konfigurierter HA-Service | nur bei explizit gemeldeten Fähigkeiten | kein eingebauter SIP-Client |

`Telegram`, `WhatsApp`, E-Mail und TTS sind damit **nicht pauschal als direkt
implementiert** zu verstehen: Sie sind nur über einen vorhandenen und
explizit konfigurierten HA-Service nutzbar. FRITZ!Box und SIP/PBX bleiben
vorbereitet, solange kein kompatibler HA-Service in der Zielumgebung
nachgewiesen ist.

Die offiziellen HA-Verträge sind [Telegram bot](https://www.home-assistant.io/integrations/telegram_bot/),
[SMTP](https://www.home-assistant.io/integrations/smtp/) und die
[TTS-Entity-/Service-Schnittstelle](https://contributors.home-assistant.io/core/entities/tts/).
Diese Links dokumentieren die tatsächlich verfügbaren HA-Aktionen; sie sind
keine Zusage, dass jede Zielinstallation den jeweiligen Provider aktiviert
oder authentifiziert hat.

## Sicherheitsgrenze

`HAServiceAdapter` ruft ausschließlich einen vorhandenen HA-Service auf. Der
Adapter kann ein konfiguriertes Empfängerziel über `target_field` in die
Service-Daten einsetzen; dadurch werden Personen, Geräte und Gruppen nicht
als proprietäre Provider-IDs interpretiert. Der Auftrag wird vor dem Aufruf
idempotent reserviert, validiert und mit einem Timeout ausgeführt. Das
Enqueue-WebSocket-Kommando legt nur einen persistenten Auftrag an. Die
`DeliveryService`-Schicht verlangt zusätzlich `authorized=True`; automatische
oder produktive Versandaktionen sind im aktuellen Entwicklungsstand gesperrt.
Alle Tests verwenden ausschließlich simulierte HA-Service-Objekte.

## Statussemantik

`accepted` bedeutet, dass Home Assistant den Dienstaufruf angenommen hat. Es
bedeutet nicht, dass ein Anbieter die Nachricht zugestellt oder ein Gerät sie
angezeigt hat. `delivery_confirmed` bleibt daher standardmäßig `false`.
