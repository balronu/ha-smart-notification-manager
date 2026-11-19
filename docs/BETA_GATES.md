# Beta-Gates

Die verbindlichen Gate-Prüfungen werden nicht durch lokale Fixtures ersetzt.

- **#16 Runtime-E2E:** eine temporäre, isolierte Home-Assistant-Core-
  Testinstanz wurde mit authentifiziertem Config Flow, WebSocket, Panel,
  Karten/Editoren, Phase-9/11-Smoke und Desktop/iPad/iPhone-Nachweisen geprüft.
  Der ausführliche Nachweis steht in `docs/ISOLATED_HA_RUNTIME_PLAN.md`.
  Die formale Schließung folgt erst nach PR- und Main-CI des Runtime-Fixes.
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
  wird dabei nicht aufgerufen. Das Gate ist nach abgeschlossenem PR und Main-CI-
  Lauf geschlossen.

Kein Gate autorisiert eine produktive Installation, Benachrichtigung, Release
oder Tag. Die öffentliche Beta bleibt bis zum Abschluss aller zwölf Phasen
gesperrt.
