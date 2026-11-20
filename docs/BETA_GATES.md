# Beta-Gates

Die verbindlichen Gate-Prüfungen werden nicht durch lokale Fixtures ersetzt.

- **#16 Runtime-E2E:** die offizielle `pytest-homeassistant`-Harness-Prüfung
  und ein authentifizierter SQLite-Regel-Speicher-/Laden-/Neustartlauf sind
  dokumentiert in `docs/GATE16_OFFICIAL_HARNESS.md`; die formale Schließung
  folgt erst nach PR- und Main-CI dieses Fixes.
- **#17 Hassfest:** wird im CI über `home-assistant/actions/hassfest` gegen den
  unveränderlichen CI-Commit ausgeführt.
- **#18 HACS:** wird im CI über `hacs/action` als Integration validiert. Der
  offizielle Lauf muss nach der autorisierten Public-Schaltung gegen den
  unveränderlichen Merge-Commit erfolgreich sein. Ein Lauf aus dem vorher
  privaten Push-Event wird als übersprungen dokumentiert und zählt nicht als
  Nachweis; der folgende öffentliche PR-Lauf ist der maßgebliche Gate-Test.
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
