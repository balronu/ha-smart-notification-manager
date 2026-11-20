# Kanal-Fähigkeitsmatrix (Phase 3)

Diese Matrix beschreibt den tatsächlich implementierten Vertrag. Ein Kanal ist
nur verfügbar, wenn der konfigurierte Home-Assistant-Dienst registriert ist.
Die Integration erfindet keine Anbieter-API und speichert keine Zugangsdaten.

| Kanal | Status | Benötigte HA-Schnittstelle | Nachgewiesene Fähigkeiten | Einschränkung |
|---|---|---|---|---|
| HA-Notify / Mobile App | implementiert | konfigurierter `notify.*`-Dienst | Nachricht, optionaler Titel, konfigurierbare Service-Daten | Fähigkeiten werden pro Kanal konfiguriert; keine Zustellgarantie |
| Telegram | über HA-Notify nutzbar | vorhandener Telegram-Notify-Dienst oder `telegram_bot.send_message`-Action | Ziel/Chat-ID wird über die konfigurierte HA-Service-Datenstruktur weitergereicht | keine direkte Telegram-API; Chat-IDs müssen in HA erlaubt sein |
| WhatsApp | externer Vertrag, im Projekt nicht direkt implementiert | Meta WhatsApp Business Cloud API oder ausdrücklich konfigurierte HA-Integration | Cloud API unterstützt template-basierte Nachrichten und liefert eine Message-ID; Zustellstatus benötigt signierte HTTPS-Webhooks | Business-Account, Phone-Number-ID, Access Token, genehmigte Templates, Webhook-Infrastruktur und externe Kosten/Ratenlimits; keine Zugangsdatenhaltung oder Webhook-Endpunkt im Projekt |
| E-Mail | über HA-Dienst nutzbar | vorhandener SMTP-Notify-Dienst bzw. `smtp.send_message`-Action | Nachricht, optionaler Titel und konfiguriertes Ziel | SMTP-Zugang und Providerzustellung nicht garantiert |
| TTS | über HA-Dienst nutzbar | vorhandener TTS-/Lautsprecher-Dienst, z. B. `tts.speak` | Nachricht, optionaler Titel und konfigurierbare Service-Daten | keine Sprachausgabe in Tests |
| FRITZ!Box-Klingeln | implementiert, externe Zielinstanz offen | `fritz.dial` mit `device_id`, `number` und `max_ring_seconds` | isoliert getesteter Rufaufbau über den offiziellen HA-Aktionsvertrag; `**9` kann interne Telefone klingeln | FRITZ!Box Tools, Click-to-Dial und Berechtigungen müssen in der Zielinstanz aktiviert sein; keine Sprache |
| SIP/PBX / Sprachanruf | technisch begrenzt, kein direkter Adapter | HA-VoIP ist für Assist über unterstützte VoIP-Adapter dokumentiert; kein generischer Alarm-Originate-Vertrag | Externes PBX kann A/B (wählen/klingeln) leisten; C/D/E (Verbindung, Ansage, Status) sind mit dem offiziellen HA-VoIP-Vertrag nicht als Smart-Notification-Zustellweg belegt | kein eingebauter SIP-Client und keine erfundene AMI-/ARI-Service-Schnittstelle |

`Telegram`, WhatsApp, E-Mail und TTS sind damit **nicht pauschal als direkt
implementiert** zu verstehen. WhatsApp Cloud API ist ein realer offizieller
Vertrag, aber diese Integration implementiert ihn derzeit nicht, weil dafür
eine geschützte Secret-Referenz, Template-/Empfängerregeln und ein signierter
Webhook-Endpunkt für Zustellstatus erforderlich wären. Eine Community-/HACS-
Bridge wird nicht als offizieller Providervertrag gewertet. FRITZ!Box ist als
konkreter Klingeladapter implementiert; die externe Zielinstanz-Abnahme bleibt
offen. SIP/PBX und Sprachanrufe bleiben ohne belegten direkten Zustelladapter
offen.

Die offiziellen Referenzen sind [Telegram bot](https://www.home-assistant.io/integrations/telegram_bot/),
[SMTP](https://www.home-assistant.io/integrations/smtp/) und die
[TTS-Entity-/Service-Schnittstelle](https://contributors.home-assistant.io/core/entities/tts/),
[FRITZ!Box `fritz.dial`](https://www.home-assistant.io/actions/fritz.dial/),
[Home-Assistant-VoIP](https://www.home-assistant.io/integrations/voip) und
[Meta WhatsApp Business Platform](https://developers.facebook.com/documentation/business-messaging/whatsapp/overview/).
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
