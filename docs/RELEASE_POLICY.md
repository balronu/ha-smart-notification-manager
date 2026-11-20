# Release-Policy

## Verbindliche Sperre

Während der zwölf Entwicklungsphasen werden keine GitHub-Releases, Beta-Tags, Stable-Tags oder HACS-Veröffentlichungen erstellt.

Die erste öffentliche Version ist ausschließlich:

```text
v1.0.0-beta.1
```

Sie darf erst veröffentlicht werden, wenn alle zwölf Phasen vollständig implementiert, integriert und getestet sind. Ein grüner Teiltest oder ein fertiger Branch ist keine Release-Freigabe.

## Release-Gates

Vor einer späteren Freigabe müssen Code, Manifest, Dokumentation, CI, HACS-Metadaten, Tests, Lizenz, Tag und Release-Body übereinstimmen. VM 104 bleibt bis zu einer gesonderten ausdrücklichen Installationsfreigabe unverändert.
