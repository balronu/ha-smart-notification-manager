# Lizenz- und Komponentenprüfung

## Projektlizenz

Der Quelltext dieses Repositorys steht unter der [MIT-Lizenz](../LICENSE).
Copyright (c) 2026 Michael Dick.

## Eingebundene Komponenten

Die Integration enthält keinen kopierten Drittanbieter-Quelltext und bündelt
keine fremden Laufzeitbibliotheken. Die Frontend-Dateien werden als eigener
Projektcode ausgeliefert.

Die für Entwicklung und Tests verwendeten Abhängigkeiten wurden vor der
Veröffentlichung geprüft:

| Komponente | Verwendung | Lizenz | Bestandteil der Auslieferung |
|---|---|---|---|
| Home Assistant Core | Laufzeit-API | Apache-2.0 | Nein, vom Host bereitgestellt |
| Home Assistant Frontend | isolierter Test-Harness | Apache-2.0 | Nein |
| pytest | Tests | MIT | Nein |
| pytest-asyncio | Tests | Apache-2.0 | Nein |
| pytest-homeassistant | Tests | Apache-2.0 | Nein |
| Ruff | Qualitätssicherung | MIT | Nein |

Die Lizenzangaben stammen aus den installierten Paketmetadaten des gepinnten
Test-Harnesses. Ein aktueller Baumscan und ein Scan der erreichbaren Git-
Historie ergaben keine Secret-Treffer. Die Prüfung ersetzt keine Prüfung
zusätzlicher Komponenten, die später als Laufzeitabhängigkeit aufgenommen
werden; solche Änderungen müssen vor Veröffentlichung erneut bewertet werden.
