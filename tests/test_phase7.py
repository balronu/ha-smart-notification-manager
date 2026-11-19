from pathlib import Path

import pytest
from smart_notification_manager.core.metrics import MetricsCoordinator
from smart_notification_manager.core.repository import SQLiteRepository


@pytest.mark.asyncio
async def test_phase7_metrics_are_aggregated_from_existing_alarm_tables(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "phase7.sqlite3")

    def seed(connection):
        connection.execute(
            "INSERT INTO rules(rule_id,name,category,enabled,created_at,updated_at,description,area_id,area_name,priority,deleted_at) VALUES (?,?,?,?,?,?,?,?,?,?,NULL)",
            ("rule-1", "Tür", "Sicherheit", 1, "2026-01-01", "2026-01-01", "", "flur", "Flur", "critical"),
        )
        connection.execute(
            "INSERT INTO alarm_instances(alarm_id,rule_id,cause_key,alarm_state,acknowledgement_state,delivery_state,escalation_state,started_at,category,priority) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("alarm-1", "rule-1", "sensor-1", "active", "unacknowledged", "pending", "none", "2026-01-01", "Sicherheit", "critical"),
        )
        connection.execute(
            "INSERT INTO delivery_attempts(attempt_id,state,attempted_at) VALUES (?,?,?)",
            ("attempt-1", "failed", "2026-01-01"),
        )

    await repository.async_run(seed)
    result = await repository.async_run(MetricsCoordinator._read)
    assert result == {
        "open_alarms": 1,
        "critical_alarms": 1,
        "unacknowledged_alarms": 1,
        "active_pauses": 0,
        "delivery_errors": 1,
        "healthy": True,
    }


def test_phase7_card_is_a_standalone_websocket_custom_card():
    source = (Path(__file__).parents[1] / "frontend" / "smart-notification-manager-card.js").read_text()
    assert 'customElements.define(CARD_TYPE' in source
    assert 'window.customCards' in source
    assert 'type: CARD_TYPE' in source
    assert 'smart_notification_manager/alarm_center/list' in source
    assert 'smart_notification_manager/alarm_center/detail' in source
    assert 'sqlite' not in source.lower()
    assert 'getConfigElement' in source and 'getStubConfig' in source
    assert source == (Path(__file__).parents[1] / "custom_components/smart_notification_manager/frontend/smart-notification-manager-card.js").read_text()


def test_phase7_fixture_documents_responsive_views_and_instances():
    fixture = Path(__file__).parents[1] / "frontend" / "phase-7-lovelace-card-fixture.html"
    source = fixture.read_text()
    assert 'data-viewport="desktop"' in source
    assert 'data-viewport="ipad-landscape"' in source
    assert 'data-viewport="ipad-portrait"' in source
    assert 'data-viewport="iphone"' in source
    assert 'data-view="compact"' in source
    assert 'data-view="list"' in source
    assert 'data-view="detail"' in source
    assert 'multi-instance' in source
