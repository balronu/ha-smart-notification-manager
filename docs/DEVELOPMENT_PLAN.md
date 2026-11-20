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
| 8 | Vorlagen, Regel-Assistent, Simulation und Regelversionierung | abgeschlossen: in `main` integriert, 97 Tests und Main-CI grün |
| 9 | Sicherer Migrationsassistent für bestehende HA-Automationen | Read-only Analyse, Hybridvorschau, externe Referenzen, Rollback-Schutz und 25 Regressionen |
| 10 | zweite Lovelace-Karte, schreibfreie Simulation, Beobachtungsmodus | keine-Aktion-Garantie mit Desktop-/iPad-/iPhone-Fixture |
| 11 | geführte Migration, Hybridbetrieb, Import/Export, Backup/Rollback und Neustart-Wiederherstellung | isolierte Abnahme ohne Sicherheitsquellen |
| 12 | HACS-/CI-/Release-Readiness und vollständige Integration | alle Gates, keine offenen Pflichttests |

Phase 1 bis Phase 11 sind im aktuellen `main`-Stand vertreten; die technische
Gate-Prüfung ist in `docs/PHASE12_ACCEPTANCE.md` nachgewiesen. Die Gates #16,
#17, #18, #19 und #24 sind verifiziert. Die fachliche Anforderungsliste enthält
jedoch weiterhin offene `O`-Einträge, insbesondere für konkrete Provider-,
Telefonie-, Statistik- und vollständige Migrationsverträge. FRITZ!Box und
SIP/PBX sind vorbereitet, nicht vollständig implementiert. Die erste
öffentliche Beta bleibt deshalb bis zur fachlichen Vollabnahme gesperrt.
