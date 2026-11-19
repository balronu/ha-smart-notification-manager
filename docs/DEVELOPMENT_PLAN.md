# Entwicklungsplan – zwölf Phasen

| Phase | Inhalt | Abnahme |
|---:|---|---|
| 1 | Fundament, Modelle, Storage, Flows, Rechtebasis, Tests | abgeschlossen: in `main` integriert, 17 Tests und GitHub-CI grün |
| 2 | Read-only HA-Discovery, Regel-/Bedingungseditor und Importmodell | abgeschlossen: PR #14 in `main`, 34 Tests und Main-CI grün |
| 3 | Regel-/Bedingungseditor und CRUD-Verträge | validierte Regelversionen |
| 4 | Empfänger, Geräte, Gruppen und Fähigkeiten | deterministische Zielprofile |
| 5 | Delivery Router und erste HA-Notify-Adapter | isolierte Mock-Zustellung |
| 6 | Alarm-Lifecycle, Bestätigung, Eskalation | Zustandsmatrix und Recovery |
| 7 | Scheduler, Ruhezeiten, Deduplizierung | Zeitfenster-/Queue-Tests |
| 8 | Audit, Diagnose, Historie, Statistiken | Fehler- und Retention-Gates |
| 9 | Frontend API und erste Lovelace-Karte | responsive Fixture-UI |
| 10 | zweite Lovelace-Karte, Simulation, Beobachtungsmodus | keine-Aktion-Garantie |
| 11 | geführte Migration, Hybridbetrieb, Backup/Rollback | Pilot ohne Sicherheitsquellen |
| 12 | HACS-/CI-/Release-Readiness und vollständige Integration | alle Gates, keine offenen Pflichttests |

Phase 1 und Phase 2 sind abgeschlossen. Phase 3 beginnt erst nach ausdrücklicher Freigabe.
Die erste öffentliche Beta bleibt bis zum Abschluss aller zwölf Phasen gesperrt.
