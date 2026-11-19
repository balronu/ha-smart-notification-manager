# Phase 5 – Benachrichtigungspolitiken

Phase 5 entwickelt die Entscheidungsschicht vor dem Delivery-System. Sie
erzeugt selbst keine Versandaufträge und ruft keine Home-Assistant-Dienste
auf.

## Entscheidungskette

1. Alarm ist `pending`, `active` oder `overdue`.
2. Regel ist aktiviert.
3. Beobachtungsmodus: simulieren und protokollieren; Critical erfordert eine
   zusätzliche Bestätigung.
4. Pause prüfen.
5. Ruhezeit prüfen.
6. Regelabhängigkeiten gegen bekannte Zustände prüfen.
7. Persistentes Rate-Limit prüfen.
8. Erst dann wird die Übergabe an Delivery erlaubt.

Jede Entscheidung erhält einen maschinenlesbaren Code und eine deutsche
Beschreibung in `policy_decisions`. Unterdrückung verändert den Alarmzustand
nicht. Critical ist standardmäßig von Ruhezeiten, Pausen und Rate-Limits
ausgenommen; eine aktivierte Critical-Beobachtung bleibt bis zur expliziten
Bestätigung unterdrückt.

## Persistenz und Zeit

Schema v6 speichert Ruhezeiten, Pausen, Rate-Limits, Rate-Limit-Ereignisse,
Abhängigkeiten, Beobachtungsmodi und Entscheidungen. Ruhezeiten verwenden eine
IANA-Zeitzone und unterstützen Zeitfenster über Mitternacht sowie Wochentage.
Pausen werden mit Ablaufzeitpunkt gespeichert und überstehen Neustarts. Die
Rate-Limit-Zählung ist von technischen Delivery-Retries und Alarmwiederholungen
getrennt.

Bei regulären Alarmversandaufträgen werden Policy-Entscheidung, Rate-Limit-
Reservierung und Auftragserstellung in einer Repository-Transaktion ausgeführt.
Preview, Beobachtungsmodus und unterdrückte Entscheidungen verbrauchen kein
Kontingent. Eine fehlgeschlagene Übergabe gibt die Reservierung nicht zurück;
technische Retries verwenden denselben Auftrag und erhöhen das Rate-Limit nicht
erneut. Eine Anbieterannahme ist weiterhin keine bestätigte Zustellung.

Die Regelabhängigkeit wird serverseitig anhand aktiver, aus der Datenbank
stammender Alarmvorgänge bewertet. Clientseitig übermittelte
`dependency_states` werden nicht als Autorität verwendet.

## WebSocket und UI

Die Admin-geschützten Verträge liegen unter `smart_notification_manager/policy/*`.
Das Panel bietet die grafische Verwaltung von Ruhezeiten und Pausen sowie die
Anzeige von Rate-Limits, Abhängigkeiten, Beobachtungsmodus und den letzten
Entscheidungen. Ungültige Eingaben werden serverseitig abgewiesen.

## Grenzen der Abnahme

Die lokalen Tests verwenden isolierte SQLite-/HA-Fixtures und simulierte
Versandadapter. Die echte authentifizierte HA-HTTP-/WebSocket-/Panel-E2E bleibt
Beta-Gate #16. Hassfest (#17), HACS (#18) und Secret-Scan (#19) bleiben vor
`v1.0.0-beta.1` verpflichtend. VM104 wird nicht verwendet.

Der admin-geschützte WebSocket-Testpfad darf nur mit `administrative_test=true`
und `test_only=true` verwendet werden. Er persistiert ausschließlich einen
Testauftrag und ruft keinen Adapter beziehungsweise keinen HA-Dienst auf.
Reguläre Aufträge benötigen eine bestehende Alarm-ID und werden immer durch die
Policy-Grenze geführt.

Die Phase-4-Methoden für fällige Alarmwiederholungen und Eskalationsstufen
ändern ausschließlich den persistenten Alarmzustand und erzeugen selbst keine
Delivery-Aufträge. Dadurch gibt es dort keinen versteckten Versandweg; sobald
ein Auftrag über den Delivery-Service oder den WebSocket-Enqueue-Vertrag
entsteht, gilt dieselbe Policy-Grenze. Das explizite Auslösen eines Alarms und
die reine Routing-Vorschau sind administrative, serverseitig geschützte
Test-/Konfigurationsaktionen und führen keinen externen Versand aus.
