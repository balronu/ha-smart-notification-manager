# Phase 8 – Vorlagen, Assistent und Simulation

Phase 8 ergänzt die bestehende Regelverwaltung um eine deutschsprachige
Vorlagenbibliothek, einen zehnstufigen Assistenten, eine serverseitige
Simulation und eine nachvollziehbare Versionshistorie.

## Vorlagen

Die 14 integrierten Vorlagen verwenden keine festen Entity-IDs. Sie beschreiben
stattdessen Platzhalter wie `<entity>`. Eigene Vorlagen werden als versioniertes
JSON exportiert. Ein Import liefert zuerst eine Konflikt- und
Fehlende-Entitäten-Vorschau und wird erst mit `confirm: true` gespeichert.
Schlüssel wie `token`, `password`, `secret` und `api_key` werden abgelehnt.

## Assistent und Simulation

Der Assistent führt durch Name/Kategorie, Entitäten, Auslöser, Bedingungen,
Routing, Wiederholung/Eskalation, Quittierung/Entwarnung und Zusammenfassung.
Der Entwurf bleibt beim Schrittwechsel erhalten und wird über den bestehenden
authentifizierten Regel-WebSocket validiert.

`smart_notification_manager/phase8/simulate` wertet einen Entwurf mit
vorgegebenen Zuständen und Policy-Gründen aus. Die Simulation schreibt weder
Alarm-, Delivery-, Rate-Limit- noch Auditdaten. Phase 8 führt keine realen
Testnachrichten, Anrufe oder TTS-Ausgaben aus.

## Versionen und Grenzen

Die letzten 20 Versionen werden angezeigt. Eine Wiederherstellung erzeugt
immer eine neue Version, überschreibt keine Historie und verlangt bei
Critical-Regeln eine ausdrückliche Bestätigung.

Die vollständige authentifizierte HA-HTTP-/WebSocket-/Panel-E2E-Prüfung ist
weiterhin Beta-Gate #16. Hassfest (#17), HACS (#18), Secret-Scan (#19) und die
automatische Delivery-Anbindung von Wiederholungen/Eskalationen (#24) bleiben
vor `v1.0.0-beta.1` verbindlich offen.
