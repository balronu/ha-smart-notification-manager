# Entwicklungsplan – zwölf Phasen

| Phase | Inhalt | Abnahme |
|---:|---|---|
| 1 | Fundament, Modelle, Storage, Flows, Rechtebasis, Tests | abgeschlossen: in `main` integriert, 17 Tests und GitHub-CI grün |
| 2 | Read-only HA-Discovery, Regel-/Bedingungseditor und Importmodell | abgeschlossen: PR #14 in `main`, 34 Tests und Main-CI grün |
| 3 | Empfänger, Kanäle und Versand-Routing | abgeschlossen: Live-WebSocket-UI, CRUD-Persistenz, Routing, Vorlagen, Versandstatus, 50 Tests und CI grün; HA-Runtime-/Panel-E2E bleibt als Gate #16 offen |
| 4 | Alarm-Lifecycle, Quittierung und Eskalation | abgeschlossen: PR #21 in `main`, serverseitige Revalidierung, Teil-/Vollquittierung, Persistenz, Eskalationsschutz, 63 Tests und Main-CI grün; echte HA-Runtime-/Panel-E2E bleibt als Gate #16 offen |
| 5 | Ruhezeiten, Pausen, Rate-Limits, Abhängigkeiten und Beobachtungsmodus | abgeschlossen: PR #23 in `main`, Policy-/Delivery-Integration, 74 Tests und Main-CI grün; automatische Wiederholungs-/Eskalationszustellung bleibt in Issue #24 offen |
| 6 | Alarmzentrale, Kategorien, Filter, Gruppierung und Benutzerrechte | auf Branch `feature/phase-6-alarm-center` implementiert; PR-/CI-Abnahme offen |
| 7 | Scheduler, Ruhezeiten, Deduplizierung | Zeitfenster-/Queue-Tests |
| 8 | Audit, Diagnose, Historie, Statistiken | Fehler- und Retention-Gates |
| 9 | Frontend API und erste Lovelace-Karte | responsive Fixture-UI |
| 10 | zweite Lovelace-Karte, Simulation, Beobachtungsmodus | keine-Aktion-Garantie |
| 11 | geführte Migration, Hybridbetrieb, Backup/Rollback | Pilot ohne Sicherheitsquellen |
| 12 | HACS-/CI-/Release-Readiness und vollständige Integration | alle Gates, keine offenen Pflichttests |

Phase 1 bis Phase 5 sind abgeschlossen und in `main` integriert. Phase 6 ist
auf einem separaten Branch implementiert, aber noch nicht in `main` integriert. Die
automatische Zustellung von Alarmwiederholungen und Eskalationen ist als
verbindlicher Beta-Vorbehalt in Issue #24 offen. Die vollständige
authentifizierte Home-Assistant-HTTP-/WebSocket-/Panel-E2E-Prüfung bleibt in
Issue #16 offen. Die Gates #17 Hassfest, #18 HACS und #19 Secret-Scan bleiben
ebenfalls vor der Beta verbindlich offen. FRITZ!Box und SIP/PBX sind
vorbereitet, nicht vollständig implementiert. Phase 6 beginnt erst nach
ausdrücklicher Freigabe.
Die erste öffentliche Beta bleibt bis zum Abschluss aller zwölf Phasen gesperrt.
