# Isolierter Home-Assistant-Runtime-Test (Gate #16)

Gate #16 bleibt offen, bis eine echte, authentifizierte Home-Assistant-
Testinstanz verfügbar ist. Die vorhandenen Python- und Chromium-Fixtures sind
wertvolle isolierte Prüfungen, ersetzen aber keine HA-Runtime.

## Voraussetzungen

1. Einen temporären Container oder eine gleichwertige isolierte Testinstanz
   mit der im Projekt festgelegten Home-Assistant-Version bereitstellen.
2. Ein frisches, nicht produktives Konfigurationsverzeichnis und eine leere
   Testdatenbank verwenden.
3. Keine Verbindung zu VM104, produktiven Geräten, produktiven Integrationen
   oder produktiven Zugangsdaten herstellen.
4. Einen ausschließlich für den Test erzeugten Benutzer mit Administrator-
   und WebSocket-Zugriff verwenden; das Kennwort darf nicht in Repository,
   Logs, Fixtures oder Artefakten erscheinen.

## Abnahmelauf

- Integration installieren und Config Flow authentifiziert abschließen.
- Initialisierung, Schema-Migrationen, SQLite, WebSocket-API und Panel prüfen.
- Beide Lovelace-Karten und ihre Editoren authentifiziert laden.
- Rechte, Fehlerpfade und Neustart-Wiederherstellung prüfen.
- Desktop-, iPad- und iPhone-Viewport mit Screenshots, DOM-/State-Marken,
  Browserfehlern, fehlgeschlagenen Requests, WebSocket-Diagnostik und
  Home-Assistant-Log erfassen.
- Nach jedem Lauf die Testinstanz und alle temporären Zugangsdaten zerstören.

## Aktueller Status

Im vorliegenden Arbeitslauf wurde keine isolierte HA-Runtime eingerichtet.
VM104 blieb unverändert. Deshalb gibt es für Gate #16 keinen authentifizierten
Runtime-Nachweis und keine Freigabeempfehlung.
