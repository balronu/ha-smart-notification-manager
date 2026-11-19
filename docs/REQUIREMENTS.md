# Verbindliche Anforderungen

Dieses Dokument ist die Phase-1-Basis für alle zwölf Entwicklungsphasen. `V` bedeutet aus den vorliegenden Anforderungen verifiziert; `O` bedeutet offen bzw. in einer späteren Detailphase zu verifizieren. Keine `O`-Anforderung wird als implementiert dargestellt.

| ID | Anforderung | Phase | Status |
|---|---|---:|---|
| R-001 | Visueller Regeleditor ohne YAML-Zwang | 3, 9 | O |
| R-002 | Sensoren, Bedingungen, Zeitfenster, Anwesenheit | 2, 3, 7 | O |
| R-003 | Prioritäten Passiv/Normal/Zeitkritisch/Critical | 3, 6 | O |
| R-004 | Alarmlebenszyklus, Bestätigung, Abschlussgrund | 6 | V als Modellziel |
| R-005 | Wiederholung, Deduplizierung, Eskalation | 6, 7 | O |
| R-006 | Personen, Geräte, Empfänger- und Kanalgruppen | 4 | O |
| R-007 | Notify, Telegram, WhatsApp, FRITZ!Box, SIP/PBX, TTS, E-Mail | 5, 12 | O; konkrete APIs zu verifizieren |
| R-008 | Klingel- und Sprachanrufe | 5, 12 | O |
| R-009 | Beobachtungsmodus und Simulation ohne Aktion | 10 | O |
| R-010 | Alarmhistorie, Tages-/Monatsstatistik | 8 | Schema vorbereitet |
| R-011 | Zwei Lovelace-Karten | 9, 10 | O |
| R-012 | Benutzerrechte und Diagnose | 1, 8 | Basis vorbereitet |
| R-013 | Import, Export und Backups | 2, 11 | O |
| R-014 | Geführte Migration bestehender HA-Automationen | 2, 11 | O; nur read-only zuerst |
| R-015 | Hybridbetrieb mit bestehenden Triggern | 11 | O |
| R-016 | Neustart-Wiederherstellung | 6, 8, 11 | O |
| R-017 | Versionierte SQLite-Datenhaltung ohne Event-Loop-Blockierung | 1 | implementiert |
| R-018 | Stabile Regel-/Alarm-IDs und aktive Duplikatsperre | 1, 6 | implementiert |
| R-019 | Keine produktiven Nachrichten/Anrufe in Phase 1 | 1 | verbindlich |
| R-020 | Öffentliche Beta erst nach allen zwölf Phasen | 12 | verbindlich |

Die vollständigen Detailanforderungen aus früheren Gesprächen müssen vor den betroffenen Phasen erneut gegen die aktuelle Anforderungsquelle abgeglichen werden.

