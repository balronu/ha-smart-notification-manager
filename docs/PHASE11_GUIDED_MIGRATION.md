# Phase 11 – Geführte Migration und Wiederherstellung

Phase 11 ordnet die verbindlichen Anforderungen **R-013** (Import, Export und
Backups), **R-014** (geführte Automation-Migration), **R-015** (Hybridbetrieb)
und **R-016** (Neustart-Wiederherstellung) zu.

## Sicherheitsmodell

Die Phase erweitert den bestehenden Phase-9-Plan. Export und Import verwenden
ein versioniertes, redigiertes JSON-Format. Import erzeugt immer einen neuen,
unbestätigten lokalen Plan. Backups werden atomar in SQLite gespeichert und
können nur bei passendem `expected_source_hash` wiederhergestellt werden.
Konflikte brechen die Transaktion vollständig ab.

Die Wiederherstellungsübersicht liest vorbereitete Pläne und externe
Alarmreferenzen nach einem Neustart. Sie verändert weder Home-Assistant-
Automationen noch Alarme oder Delivery-Daten. Die stabile Zuordnung aus
`automation_id` und `execution_ref` bleibt idempotent.

## Geführte Oberfläche

`phase-11-guided-migration.js` stellt deutsche Export-, Sicherungs- und
Recovery-Aktionen bereit. Die ursprüngliche Automation bleibt aktiv und eine
Aktivierung benötigt weiterhin eine separate Bestätigung. Der Hybridplan aus
Phase 9 erhält Trigger, Bedingungen, Variablen, Wartezeiten, `choose`, `if`,
`repeat` und sonstige Aktionen; nur ausgewählte Benachrichtigungen werden
ersetzt.

Issue #12 und Milestone Phase 11 bleiben bis zur Review offen. VM104 und
produktive HA-Automationen werden nicht verwendet.
