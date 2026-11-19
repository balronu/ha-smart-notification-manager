# Phase 10 – Beobachtungsmodus und Simulation

Diese Phase ordnet die vorhandenen Anforderungen **R-009** (Simulation ohne
Aktion) und **R-011** (zweite Lovelace-Karte) zu. Die Karte
`smart-notification-manager-observation-card` verwendet ausschließlich die
authentifizierte, schreibfreie Vorschau-API.

## Sicherheitsgarantie

`smart_notification_manager/phase10/observe` ruft die bestehende Simulation
und Policy-Vorschau auf. Es entstehen keine Alarm-, Delivery-, Rate-Limit-,
Policy- oder Audit-Einträge. Die Karte zeigt „Simulation · Keine produktive
Aktion“ und besitzt keine produktive Aktivierung. Unvollständige
Zustandsdaten werden als „Nicht sicher bestimmbar“ angezeigt.

Die isolierte Fixture `frontend/phase-10-observation-card-fixture.html` deckt
Desktop, iPad quer/hoch und iPhone ab. Issue #11 und Milestone Phase 10
bleiben bis zur Review und den offenen Beta-Gates offen.
