# Phase 12 – Anforderungsmatrix

Stand: 2026-11-20. Diese Matrix ist ein Arbeitsnachweis und kein Beta-
Freigabedokument. `Erfüllt` wird nur verwendet, wenn Implementierung,
isolierter Test und die vorgesehene Bedienoberfläche nachgewiesen sind.

| Anforderung | Soll-Funktion | Ist-Zustand | Fehlende Implementierung / Grenze | Testnachweis | Status |
|---|---|---|---|---|---|
| R-001 | Deutscher visueller Regeleditor ohne YAML-Zwang | Regeleditor mit WebSocket-Persistenz vorhanden | Browser-E2E des vollständigen Flows muss in Phase 12 noch gebündelt nachgewiesen werden | `tests/test_frontend.py`, `tests/test_websocket.py`, Gate-16-UI-Nachweis | teilweise |
| R-002 | Sensoren, Bedingungen, Zeitfenster, Anwesenheit | Trigger-/Bedingungsmodelle und Simulation vorhanden | Vollständige UI-Abdeckung der Bedingungstypen und Runtime-Abnahme ausstehend | `tests/test_rules.py`, `tests/test_phase10.py` | teilweise |
| R-003 | Vier Prioritätsstufen | Prioritätsmodell und Persistenz vorhanden | Sichtbare Ende-zu-Ende-Abnahme aller Stufen ausstehend | `tests/test_rules.py`, `tests/test_alarm_lifecycle.py` | teilweise |
| R-004 | Alarmlebenszyklus, Bestätigung, Abschlussgrund | Trigger, Aktivierung, Bestätigung, Auflösung, Schließgrund und Recovery implementiert | Keine bekannte Kernlücke; Gesamt-UI-Nachweis noch offen | `tests/test_alarm_lifecycle.py`, `tests/test_phase4_revalidation.py` | erfüllt (isoliert) |
| R-005 | Wiederholung, Deduplizierung, Eskalation | Policy-Entscheidungen, Wiederholungen, Eskalationsstufen und Idempotenz vorhanden | Vollständige Provider-Zustellung im Runtime-Test noch offen | `tests/test_policies.py`, `tests/test_alarm_lifecycle.py`, `tests/test_delivery_lifecycle.py` | teilweise |
| R-006 | Personen, Geräte, Empfänger- und Kanalgruppen | Recipient-/Channel-Store und Rollenprüfung vorhanden | Gruppenbedienung und Browser-E2E ausstehend | `tests/test_recipient_store.py`, `tests/test_websocket.py` | teilweise |
| R-007 | Notify, Telegram, WhatsApp, FRITZ!Box, SIP/PBX, TTS, E-Mail | Expliziter Kanal-Katalog; validierte HA-Service-Domänen für Notify, Telegram (`telegram_bot`/Notify), SMTP/E-Mail (`smtp`/Notify) und TTS (`tts`) | WhatsApp, FRITZ!Box und SIP/PBX besitzen im Projekt weiterhin keinen belegten direkten Provider-Adapter; externe HA-Integration, Berechtigungen und Zugangsdaten müssen separat nachgewiesen werden | `tests/test_delivery_lifecycle.py`, `tests/test_recipient_store.py`, `tests/test_phase12_runtime.py` | teilweise; externe Abnahme offen |
| R-008 | Klingel- und Sprachanrufe | Kanaltypen und HA-Service-Vertrag vorbereitet | Kein direkter Telefonie-/Klingelprovider darf erfunden werden; konkrete verfügbare HA-Integration und isolierter Adaptertest fehlen | Kanal-Katalogtest | offen / externer Vertrag |
| R-009 | Beobachtung und Simulation ohne Aktion | Simulation und Beobachtung liefern Vorschau ohne Alarm-/Delivery-Zeilen | Vollständige UI-E2E und alle Fehlerszenarien ausstehend | `tests/test_phase10.py`, `tests/test_phase9.py` | teilweise |
| R-010 | Historie, Tages-/Monatsstatistik mit Zustellstatus | Persistente Statistik-Store-Abfrage mit verschachteltem UI-Filtervertrag, inklusivem Kalender-Enddatum, Tages-/Monatsaggregation und Neustart-Readback; deutsches Panel zeigt Tages- und Monatswerte | Browser-E2E und vollständige UI-Abnahme ausstehend | `tests/test_statistics.py`, `tests/test_frontend.py` | teilweise |
| R-011 | Zwei Lovelace-Karten | Beobachtungs-/Simulationskarte und Alarm-Center-Karte vorhanden | Responsive Browser-E2E der vollständigen Phase-12-Oberfläche ausstehend | `tests/test_phase10.py`, `tests/test_phase11.py`, Frontend-Fixtures | teilweise |
| R-012 | Rechte, Diagnose, Fehlermeldungen | Rollenprüfungen, stabile Fehlercodes und Diagnosepfade vorhanden | End-to-End-Matrix der Rollen im Browser ausstehend | `tests/test_policies.py`, `tests/test_websocket.py` | teilweise |
| R-013 | Import, Export, Backup/Restore | Redigierter Export, bestätigter Import, atomisches Backup/Restore und Konfliktprüfung vorhanden | UI-E2E und Gesamtregression ausstehend | `tests/test_phase11.py` | erfüllt (isoliert) |
| R-014 | Geführte Automation-Migration | Discovery, Vorschau, sichtbare Vorbereitung/Bestätigung/Rollback sowie Export/Import/Backup/Recovery vorhanden; keine HA-Automation wird automatisch geschrieben | Authentifizierte Browser-E2E und reale HA-YAML-Varianten als isolierte Fixtures bleiben ausstehend | `tests/test_phase9.py`, `tests/test_phase11.py` | teilweise |
| R-015 | Hybridbetrieb mit vorhandenen Triggern | Selektive Ersetzung in `choose`/`repeat`/`parallel` bei Erhalt der übrigen Automation vorhanden | Keine HA-Automation wird automatisch geschrieben; Aktivierung bleibt bewusst freigabepflichtig | `tests/test_phase9.py`, `tests/test_phase11.py` | erfüllt (read-only) |
| R-016 | Neustart-Recovery | Pläne und externe Referenzen werden aus SQLite wiederhergestellt | Restart-E2E in isolierter HA-Runtime noch ausstehend | `tests/test_phase11.py` | erfüllt (SQLite isoliert) |
| R-017 | Versionierte, event-loop-sichere SQLite-Datenhaltung | Repository führt Migrationen im Worker-Thread aus | Keine bekannte Kernlücke | `tests/test_storage.py`, Vollregression | erfüllt |
| R-018 | Stabile IDs und Duplikatsperre | UUID5-Migrationsregel, SQLite-Eindeutigkeit und idempotente Referenzen vorhanden | Keine bekannte Kernlücke | `tests/test_alarm_lifecycle.py`, `tests/test_phase11.py` | erfüllt (isoliert) |
| R-019 | Keine produktiven Zustellungen in der Entwicklungsphase | Tests verwenden Fixtures/Mocks; keine Produktiv-HA-Schreibvorgänge | Vor Beta muss ein separater autorisierter Provider-Abnahmepfad definiert werden | Vollregression und Runtime-Protokolle | erfüllt als Sicherheitsgate |
| R-020 | Beta erst nach vollständiger Abnahme | Issue #13 bleibt offen, kein Tag/Release | Alle `teilweise`/`offen`-Zeilen, CI/Hassfest/HACS, Browser- und Runtime-Nachweise schließen | `docs/PHASE12_ACCEPTANCE.md` | offen |

## Verbindliche Testspur

Die lokale Basisregression wird mit `uv run pytest`, `uv run ruff check .`,
`uv run python -m compileall custom_components` und JavaScript-Syntax-/Mirror-
Prüfungen ausgeführt. Vor jedem Merge kommen exakter PR-Head, Hassfest,
HACS und Main-CI hinzu. Ein grüner Infrastrukturcheck ersetzt keinen
fachlichen Nachweis und ist daher in dieser Matrix separat zu behandeln.

## Sicherheits- und Veröffentlichungsgrenze

Diese Implementierung schreibt keine produktive HA-Automation und löst keine
echte Nachricht, TTS-Ausgabe, Klingel oder Telefonie aus. Provider, die
externe Zugangsdaten, Freischaltungen oder Kosten benötigen, bleiben bis zu
einem ausdrücklich autorisierten isolierten Abnahmetest eine dokumentierte
externe Abhängigkeit. VM104 und produktive Daten bleiben unverändert.
