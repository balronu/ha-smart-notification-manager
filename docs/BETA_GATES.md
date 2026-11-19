# Beta-Gates

Die verbindlichen Gate-Prüfungen werden nicht durch lokale Fixtures ersetzt.

- **#16 Runtime-E2E:** benötigt eine gepinnte, isolierte Home-Assistant-
  Testinstanz mit authentifizierter Panel-/WebSocket-Prüfung. VM104 wird nicht
  verwendet.
- **#17 Hassfest:** wird im CI über `home-assistant/actions/hassfest` gegen den
  unveränderlichen CI-Commit ausgeführt.
- **#18 HACS:** wird im CI über `hacs/action` als Integration validiert, sobald
  das Repository öffentlich ist. Der aktuelle offizielle Lauf ist wegen der
  privaten Repository-Sichtbarkeit nicht ausführbar; das Gate bleibt offen.
- **#19 Secret-Scan:** `detect-secrets` prüft den aktuellen Baum und ein
  Dummy-Sentinel; zusätzlich wurde die Git-Historie mit 358 Blobs geprüft.
- **#24 Wiederholung/Eskalation:** wird über den zentralen, policy-geprüften
  Delivery-Planer mit simulierten Adaptern, Neustart und paralleler Verarbeitung
  nachgewiesen. Die Übergabe erzeugt nur idempotente Delivery-Jobs; ein Adapter
  wird dabei nicht aufgerufen. Das Gate bleibt bis zum abgeschlossenen PR und
  Main-CI-Lauf offen.

Kein Gate autorisiert eine produktive Installation, Benachrichtigung, Release
oder Tag. Die öffentliche Beta bleibt bis zum Abschluss aller zwölf Phasen
gesperrt.
