# Entwicklungsplan – zwölf Phasen

| Phase | Inhalt | Abnahme |
|---:|---|---|
| 1 | Fundament, Modelle, Storage, Flows, Rechtebasis, Tests | abgeschlossen: in `main` integriert, 17 Tests und GitHub-CI grün |
| 2 | Read-only HA-Discovery, Regel-/Bedingungseditor und Importmodell | abgeschlossen: PR #14 in `main`, 34 Tests und Main-CI grün |
| 3 | Empfänger, Kanäle und Versand-Routing | abgeschlossen: Live-WebSocket-UI, CRUD-Persistenz, Routing, Vorlagen, Versandstatus, 50 Tests und CI grün; HA-Runtime-/Panel-E2E bleibt als Gate #16 offen |
| 4 | Alarm-Lifecycle, Quittierung und Eskalation | abgeschlossen: PR #21 in `main`, serverseitige Revalidierung, Teil-/Vollquittierung, Persistenz, Eskalationsschutz, 63 Tests und Main-CI grün; echte HA-Runtime-/Panel-E2E bleibt als Gate #16 offen |
| 5 | Ruhezeiten, Pausen, Rate-Limits, Abhängigkeiten und Beobachtungsmodus | abgeschlossen: PR #23 in `main`, Policy-/Delivery-Integration, 74 Tests und Main-CI grün; automatische Wiederholungs-/Eskalationszustellung bleibt in Issue #24 offen |
| 6 | Alarmzentrale, Kategorien, Filter, Gruppierung und Benutzerrechte | abgeschlossen: PR #26 in `main`, 79 Tests und Main-CI grün; Runtime-/Beta-Gates bleiben offen |
| 7 | Lovelace-Alarmkarte, grafischer Karteneditor und native HA-Entitäten | abgeschlossen: PR #28 in `main`, 85 Tests und Main-CI grün; Runtime-/Beta-Gates bleiben offen |
| 8 | Vorlagen, Regel-Assistent, Simulation und Regelversionierung | 14 Vorlagen, sichere Simulation, Versions- und Restore-Tests |
| 9 | Frontend API und erste Lovelace-Karte | responsive Fixture-UI |
| 10 | zweite Lovelace-Karte, Simulation, Beobachtungsmodus | keine-Aktion-Garantie |
| 11 | geführte Migration, Hybridbetrieb, Backup/Rollback | Pilot ohne Sicherheitsquellen |
| 12 | HACS-/CI-/Release-Readiness und vollständige Integration | alle Gates, keine offenen Pflichttests |

Phase 1 bis Phase 7 sind abgeschlossen und in `main` integriert. Phase 8 ist
in Entwicklung. Die
automatische Zustellung von Alarmwiederholungen und Eskalationen ist als
verbindlicher Beta-Vorbehalt in Issue #24 offen. Die vollständige
authentifizierte Home-Assistant-HTTP-/WebSocket-/Panel-E2E-Prüfung bleibt in
Issue #16 offen. Die Gates #17 Hassfest, #18 HACS und #19 Secret-Scan bleiben
ebenfalls vor der Beta verbindlich offen. FRITZ!Box und SIP/PBX sind
vorbereitet, nicht vollständig implementiert. Phase 9 beginnt erst nach
ausdrücklicher Freigabe von Phase 8.
Die erste öffentliche Beta bleibt bis zum Abschluss aller zwölf Phasen gesperrt.
