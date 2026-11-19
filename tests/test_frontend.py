from pathlib import Path

FRONTEND = Path(__file__).parents[1] / "frontend" / "smart-notification-manager.js"


def test_frontend_is_a_visual_editor_and_has_mobile_layout_contract():
    source = FRONTEND.read_text(encoding="utf-8")
    assert "smart-notification-rule-editor" in source
    assert "Neue Regel" in source
    assert "data-action=\"add-condition\"" in source
    assert "@media(max-width:520px)" in source
    assert "textarea" in source
    assert 'data-field="json"' not in source
    assert "smart-notification-recipient-manager" in source
    assert "Empfänger und Kanäle" in source
    assert "smart_notification_manager/recipient/save" in source
    assert "smart-notification-phase3-manager" in source
    assert "smart_notification_manager/channel-group/save" in source
    assert "smart_notification_manager/template/save" in source
    assert "smart_notification_manager/routing/preview" in source
    assert "smart_notification_manager/rule/routing/save" in source
    assert "smart_notification_manager/delivery/list" in source
    assert (FRONTEND.parent / "phase-3-fixture.html").exists()
    assert (FRONTEND.parent / "phase-3-live-fixture.html").exists()
