from pathlib import Path

FRONTEND = Path(__file__).parents[1] / "frontend" / "smart-notification-manager.js"


def test_frontend_is_a_visual_editor_and_has_mobile_layout_contract():
    source = FRONTEND.read_text(encoding="utf-8")
    assert "smart-notification-rule-editor" in source
    assert "Neue Regel" in source
    assert "data-action=\"add-condition\"" in source
    assert 'addEventListener("click", this._clickHandler)' in source
    assert 'addEventListener("input", this._inputHandler)' in source
    assert 'addEventListener("change", this._changeHandler)' in source
    assert 'if (action === "add-condition") { this.syncForm();' in source
    assert "@media(max-width:520px)" in source
    assert "textarea" in source
    assert 'data-field="json"' not in source
    assert "smart-notification-recipient-manager" in source
    assert "Empfänger und Kanäle" in source
    assert "smart_notification_manager/recipient/save" in source
    assert "smart-notification-phase3-manager" in source
    assert "smart_notification_manager/channel-group/save" in source
    assert "channel_catalog" in source
    assert "Empfänger-Zielfeld" in source
    assert "target_field" in source
    assert "smart_notification_manager/template/save" in source
    assert "smart_notification_manager/routing/preview" in source
    assert "smart_notification_manager/rule/routing/save" in source
    assert "smart_notification_manager/delivery/list" in source
    assert "smart-notification-phase4-alarm-manager" in source
    assert "smart_notification_manager/alarm/list" in source
    assert "smart_notification_manager/alarm/acknowledge" in source
    assert "smart_notification_manager/alarm/resolve" in source
    assert "smart_notification_manager/alarm/close" in source
    assert "smart_notification_manager/alarm/acknowledge_many" in source
    assert "smart-notification-phase6-alarm-center" in source
    assert "smart_notification_manager/alarm_center/list" in source
    assert "smart_notification_manager/alarm_center/detail" in source
    assert "Alarmzentrale" in source
    assert "smart-notification-phase5-policy-manager" in source
    assert "smart_notification_manager/policy/quiet/save" in source
    assert "smart_notification_manager/policy/pause/save" in source
    assert "policy/list" in source
    assert "Ruhezeiten, Pausen und Richtlinien" in source
    assert "smart-notification-phase12-statistics" in source
    assert "smart_notification_manager/statistics/get" in source
    assert "Alarmstatistiken" in source
    assert "Auswahl quittieren" in source
    assert "teilweise quittiert" in source
    assert "vollständig quittiert" in source
    assert source == (FRONTEND.parent.parent / "custom_components" / "smart_notification_manager" / "frontend" / "smart-notification-manager.js").read_text(encoding="utf-8")
    assert (FRONTEND.parent / "phase-3-fixture.html").exists()
    assert (FRONTEND.parent / "phase-3-live-fixture.html").exists()
    assert (FRONTEND.parent / "phase-4-alarm-fixture.html").exists()
    assert (FRONTEND.parent / "phase-6-alarm-center-fixture.html").exists()
    assert (FRONTEND.parent / "phase-5-policy-fixture.html").exists()
    assert (FRONTEND.parent / "phase-9-automation-migration-fixture.html").exists()
    assert (FRONTEND.parent / "phase-12-statistics-fixture.html").exists()
    phase9 = FRONTEND.parent / "phase-9-automation-migration.js"
    assert phase9.exists()
    source9 = phase9.read_text(encoding="utf-8")
    assert "Automationen entdecken" in source9
    assert "smart_notification_manager/phase9/discover" in source9
    assert "Keine automatische Änderung" in source9
    assert "@media(max-width:650px)" in source9
