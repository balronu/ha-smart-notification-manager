from pathlib import Path

FRONTEND = Path(__file__).parents[1] / "frontend" / "smart-notification-manager.js"


def test_frontend_is_a_visual_editor_and_has_mobile_layout_contract():
    source = FRONTEND.read_text(encoding="utf-8")
    assert "smart-notification-rule-editor" in source
    assert "Neue Regel" in source
    assert "data-action=\"add-condition\"" in source
    assert "@media(max-width:520px)" in source
    assert "textarea" in source
    assert "JSON" not in source
