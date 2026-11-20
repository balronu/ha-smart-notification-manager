# Phase 12 – Abnahmebericht

Stand: 2026-11-20. **Nicht bereit für Beta.**

## Verifizierte Release-Gates

| Nachweis | Ergebnis |
|---|---|
| Lizenz | MIT, Copyright (c) 2026 Michael Dick, in PR #41 |
| PR #41 | gemergt mit `e84fcf5114cc3e33a23139c3465b709909296e92` |
| PR #41 Head-CI/Hassfest | PASS auf `bafee1c1e708e3daef223add920fe01677afab33` |
| Public-Schaltung | Repository `balronu/ha-smart-notification-manager`, verifiziert PUBLIC |
| HACS-Korrekturen | Topics und lokales Branding in PR #42 |
| HACS-Gate #18 | PASS auf `a92396b35d1f0b39ffbe07200d1d9fd93d67876c` |
| PR #42 | gemergt mit `21ed5467e159c51f40782283d25598be442b22d6` |
| Main-CI nach PR #42 | PASS auf `21ed5467e159c51f40782283d25598be442b22d6` |
| Secret-Scan | aktueller Baum und erreichbare Historie ohne Treffer |

Die HACS-Prüfung wurde zunächst wegen fehlender Topics und Brand-Assets
abgelehnt. Beide Befunde wurden behoben und im anschließenden öffentlichen
PR-Lauf erfolgreich erneut geprüft. Gate #18 ist damit geschlossen.

## Verbindliche Klarstellung zu optionalen Providern

Telegram, WhatsApp sowie sämtliche Telefoniekanäle (FRITZ!Box, SIP/PBX,
Klingel- und Sprachanrufe) sind nach der Projektentscheidung optionale
Erweiterungen. Ihre Installation, externe Verfügbarkeit oder Zielinstanz-
Abnahme ist keine Voraussetzung für die erste Beta. Der Kernbetrieb muss ohne
diese Integrationen funktionieren.

Die UI kennzeichnet fehlende optionale Dienste als `Nicht eingerichtet` oder
`Nicht verfügbar`. Ein gespeicherter Kanal wird nur bei einem vorhandenen
HA-Service als verfügbar angezeigt; die Delivery-Schicht validiert den Dienst
vor dem Aufruf und persistiert fehlende Voraussetzungen als Fehler statt als
erfolgreiche Zustellung. Config-Flow, Panel, Regeleditor, Statistik und
Migration benötigen keine optionalen Provider.

## Verbleibende fachliche Blocker

Die Beta bleibt trotz optionaler Provider gesperrt, bis die verbindlichen
Kernanforderungen, die authentifizierte isolierte HA-Browser-/Runtime-Abnahme
und die übrigen Release-Gates nachgewiesen sind. Issue #13 bleibt offen.

Es wurden kein Tag, kein Release, keine HACS-Installation und keine
produktive Home-Assistant-Änderung vorgenommen.
