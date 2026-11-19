from pathlib import Path

from smart_notification_manager.core.simulation import simulate_rule

ROOT = Path(__file__).parents[1]


def _rule():
    return {"rule_id": "phase10-rule", "name": "Tür", "description": "", "category": "Sicherheit", "priority": "normal", "enabled": True, "version": 1, "triggers": [{"kind": "state", "entity_ids": ["binary_sensor.tuer"], "to_state": "on", "delay_seconds": 30}], "conditions": {"kind": "all", "children": [{"kind": "entity_state", "value": {"entity_id": "binary_sensor.tuer", "state": "on"}}]}, "routing": {"recipient_ids": ["person:test"], "channel_ids": ["mobile_app"]}}


def test_phase10_observation_card_is_mirrored_and_read_only():
    source = (ROOT / "frontend/smart-notification-manager-observation-card.js").read_text()
    assert source == (ROOT / "custom_components/smart_notification_manager/frontend/smart-notification-manager-observation-card.js").read_text()
    assert 'smart_notification_manager/phase10/observe' in source
    assert 'data-action-guarantee="no-action"' in source
    assert 'Keine produktive Aktion' in source and 'window.customCards' in source


def test_phase10_simulation_reports_missing_data_without_delivery_claim():
    result = simulate_rule(_rule(), states={})
    assert result["would_send"] is False
    assert result["data_complete"] is False
    assert "Nicht sicher bestimmbar" in result["delivery_reason"]
    assert result["earliest_delivery"] is None


def test_phase10_simulation_exposes_delay_and_routing_without_action():
    result = simulate_rule(_rule(), states={"binary_sensor.tuer": {"before": "off", "after": "on"}})
    assert result["would_send"] is True and result["earliest_delivery"]
    assert result["recipients"] == ["person:test"] and result["channels"] == ["mobile_app"]
    assert not any(key in result for key in ("alarm_id", "delivery_attempt_id"))


def test_phase10_fixture_documents_required_viewports_and_no_action():
    fixture = (ROOT / "frontend/phase-10-observation-card-fixture.html").read_text()
    for marker in ("desktop", "ipad-landscape", "ipad-portrait", "iphone"):
        assert f'data-viewport="{marker}"' in fixture
    assert "Keine produktive Aktion" in fixture and "Beobachtungsmodus" in fixture
