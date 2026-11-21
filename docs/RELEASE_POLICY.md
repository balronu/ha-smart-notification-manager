# Release-Policy

## Veröffentlichungsentscheidung

Während der zwölf Entwicklungsphasen werden grundsätzlich keine Releases
erstellt. Für den ausdrücklich autorisierten manuellen Teststand gilt folgende
begrenzte Ausnahme:

Die erste öffentliche Version war:

```text
v0.1.0-beta.1
```

Die aktuelle manuelle Test-Beta ist:

```text
v0.1.0-beta.11
```

Diese Beta ist kein Nachweis der vollständigen Produktabnahme. Die
authentifizierte Browser-E2E darf für diesen manuellen Teststand offen bleiben
und muss in den Release Notes als Limitierung genannt werden. Eine Stable-
Veröffentlichung bleibt bis zur vollständigen Abnahme ausgeschlossen.

## Release-Gates

Vor einer späteren Freigabe müssen Code, Manifest, Dokumentation, CI, HACS-Metadaten, Tests, Lizenz, Tag und Release-Body übereinstimmen. VM 104 bleibt bis zu einer gesonderten ausdrücklichen Installationsfreigabe unverändert.
