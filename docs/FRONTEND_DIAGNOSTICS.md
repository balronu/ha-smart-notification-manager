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
