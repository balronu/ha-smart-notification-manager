# Kanal-Fähigkeitsmatrix (Phase 3)

Diese Matrix beschreibt den tatsächlich implementierten Vertrag. Ein Kanal ist
nur verfügbar, wenn der konfigurierte Home-Assistant-Dienst registriert ist.
Die Integration erfindet keine Anbieter-API und speichert keine Zugangsdaten.

| Kanal | Status | Benötigte HA-Schnittstelle | Nachgewiesene Fähigkeiten | Einschränkung |
|---|---|---|---|---|
| HA-Notify / Mobile App | implementiert | konfigurierter `notify.*`-Dienst | Nachricht, optionaler Titel, konfigurierbare Service-Daten | Fähigkeiten werden pro Kanal konfiguriert; keine Zustellgarantie |
| Telegram | über HA-Notify nutzbar | vorhandener Telegram-Notify-Dienst | wie vom HA-Dienst gemeldet/konfiguriert | keine direkte Telegram-API |
| WhatsApp | vorbereitet über HA-Integration | vorhandener HA-Dienst der Integration | nur explizit konfigurierte Fähigkeiten | keine proprietäre API |
| E-Mail | über HA-Dienst nutzbar | vorhandener Mail-/Notify-Dienst | Nachricht, optionaler Titel | Anbieterzustellung nicht garantiert |
| TTS | über HA-Dienst nutzbar | vorhandener TTS-/Lautsprecher-Dienst | kanalabhängige Service-Daten | keine Sprachausgabe in Tests |
| FRITZ!Box-Klingeln | vorbereitet | vorhandener HA-Service | nur Klingelaktion, keine Sprache | Klingeln und TTS bleiben getrennt |
| SIP/PBX-TTS | vorbereitet | vorhandener konfigurierter HA-Service | nur bei explizit gemeldeten Fähigkeiten | kein eingebauter SIP-Client |

## Sicherheitsgrenze

`HAServiceAdapter` ruft ausschließlich einen vorhandenen HA-Service auf. Das
Enqueue-WebSocket-Kommando legt nur einen persistenten Auftrag an. Die
`DeliveryService`-Schicht verlangt zusätzlich `authorized=True`; automatische
oder produktive Versandaktionen sind im aktuellen Entwicklungsstand gesperrt.
Alle Tests verwenden ausschließlich simulierte HA-Service-Objekte.

## Statussemantik

`accepted` bedeutet, dass Home Assistant den Dienstaufruf angenommen hat. Es
bedeutet nicht, dass ein Anbieter die Nachricht zugestellt oder ein Gerät sie
angezeigt hat. `delivery_confirmed` bleibt daher standardmäßig `false`.
