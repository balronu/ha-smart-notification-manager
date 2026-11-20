# Beta-Gates

Die verbindlichen Gate-Prüfungen werden nicht durch lokale Fixtures ersetzt.

- **#16 Runtime-E2E:** PASS; die offizielle `pytest-homeassistant`-
  Harness-Prüfung und der authentifizierte SQLite-Regel-Speicher-/Laden- und
  Neustartlauf sind in `docs/GATE16_OFFICIAL_HARNESS.md` dokumentiert.
- **#17 Hassfest:** PASS auf den geprüften PR- und Main-Commits über
  `home-assistant/actions/hassfest`.
- **#18 HACS:** wird im CI über `hacs/action` als Integration validiert. Der
  offizielle Lauf muss nach der autorisierten Public-Schaltung gegen den
  unveränderlichen Merge-Commit erfolgreich sein. Ein Lauf aus dem vorher
  privaten Push-Event wird als übersprungen dokumentiert und zählt nicht als
  Nachweis; der folgende öffentliche PR-Lauf ist der maßgebliche Gate-Test.
- **#19 Secret-Scan:** PASS; `detect-secrets` prüft den aktuellen Baum und ein
  Dummy-Sentinel. Die erreichbare Git-Historie wurde zusätzlich geprüft.
- **#24 Wiederholung/Eskalation:** PASS; wird über den zentralen, policy-geprüften
  Delivery-Planer mit simulierten Adaptern, Neustart und paralleler Verarbeitung
  nachgewiesen. Die Übergabe erzeugt nur idempotente Delivery-Jobs; ein Adapter
  wird dabei nicht aufgerufen.

Kein Gate autorisiert eine produktive Installation, Benachrichtigung, Release
oder Tag. Die öffentliche Beta bleibt bis zum Abschluss aller zwölf Phasen
gesperrt.
