# Frontend-Diagnose / Frontend diagnostics

## Deutsch

Beta 4 enthält einen opt-in Diagnosemodus für das Panel und den visuellen
Regeleditor. Er ist standardmäßig deaktiviert und protokolliert keine
Eingabewerte, Tokens, Cookies oder personenbezogenen Daten.

Aktivierung für einen lokalen Test:

```text
/smart_notification_manager?snm_debug=1
```

Alternativ kann vor dem Öffnen des Panels im Browser gesetzt werden:

```js
localStorage.setItem("smart_notification_manager_debug", "1")
```

Die Browser-Konsole enthält dann nur Build-Kennung, Panel-/Editor-Instanz,
Lebenszyklusereignisse, Render-Anzahl, Ursachen sowie den Status des vorher
aktiven Elements. Die eindeutige Build-Kennung ist außerdem als
`data-snm-build="beta4-editor-lifecycle"` am Panel-Host sichtbar.

Zum Deaktivieren:

```js
localStorage.removeItem("smart_notification_manager_debug")
```

Die Diagnoseausgabe ist kein Ersatz für eine authentifizierte HA-Browser-E2E.

## Eigenständige iPhone-Diagnose

Beta 5 stellt zusätzlich eine unabhängige, durch Home Assistant geschützte
Diagnoseseite bereit:

```text
/api/smart_notification_manager/diagnostics
```

Sie funktioniert unabhängig vom normalen Panel-Bundle und prüft die
Erreichbarkeit der veröffentlichten `smart-notification-manager.js?v=4`, die
Custom-Element-Registrierung, den initialen Render, JavaScript-Fehlerkanäle
und den HA-WebSocket-Handshake. Die Seite erzeugt keinen Zugriffstoken und
sendet keinen Bericht an externe Server. Der WebSocket-Test prüft nur den
`auth_required`-Handshake; er behauptet keine authentifizierte
WebSocket-Funktion, wenn kein regulärer HA-Login-Kontext dafür vorliegt.

### iPhone-Anleitung

1. In Safari oder der Companion-App anmelden und die obige URL auf demselben
   HA-Host öffnen.
2. **Diagnose starten** drücken und warten, bis alle Prüfungen einen Status
   haben. Es gibt keine endlose Ladeanzeige.
3. **Bereinigten Bericht kopieren** drücken.
4. Den Bericht nur als Text in einem privaten GitHub-Issue oder direkt an den
   Projektbetreuer senden. Er enthält keine Cookies, Tokens oder
   Eingabewerte; User-Agent und technische Statusinformationen bleiben zur
   Fehleranalyse enthalten.

Wenn die Diagnose-URL selbst nicht lädt, ist das ein authentifizierter
Home-Assistant-HTTP-/Installationsfehler. Bitte nur HTTP-Status und URL-Pfad
melden, niemals Session-URLs oder Zugangsdaten.

## English

Beta 4 includes an opt-in diagnostic mode for the panel and visual rule
editor. It is disabled by default and does not log field values, tokens,
cookies, or personal data. Enable it with `?snm_debug=1` on the panel URL or
with `localStorage.setItem("smart_notification_manager_debug", "1")`.

Console records contain only the build ID, panel/editor instance, lifecycle
events, render counts, causes, and whether the previously active element was
still connected. The panel host exposes the build ID as
`data-snm-build="beta4-editor-lifecycle"`. This diagnostic mode does not
replace authenticated Home Assistant browser E2E.

The standalone authenticated diagnostic page is available at
`/api/smart_notification_manager/diagnostics`. It is intentionally independent
of the panel bundle and reports only same-origin resource, initialization,
error-channel, and WebSocket handshake status. It does not expose tokens or
send telemetry.
