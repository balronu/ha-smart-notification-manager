from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from homeassistant.exceptions import HomeAssistantError
from smart_notification_manager.core.metrics import MetricsCoordinator
from smart_notification_manager.core.repository import SQLiteRepository
from smart_notification_manager.core.rules import ConditionNode, Priority, RuleDefinition
from smart_notification_manager.switch import RuleSwitch, async_sync_rule_switches


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


def _rule(rule_id="rule-1", *, version=1, enabled=True, priority=Priority.NORMAL, name="Regel"):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return RuleDefinition(
        rule_id, name, "", None, None, "Sonstiges", priority, enabled,
        (), ConditionNode("all", children=()), version, now, now,
    )


@pytest.mark.asyncio
async def test_rule_switch_refresh_adds_updates_and_marks_deleted_rules():
    class Store:
        async def async_list(self):
            return [_rule("new", name="Neue Regel")]

    coordinator = SimpleNamespace(last_update_success=True)
    old = RuleSwitch(Store(), coordinator, SimpleNamespace(entry_id="entry"), _rule("old"))
    old.async_write_ha_state = lambda: None
    entities = {"old": old}
    added = []
    await async_sync_rule_switches(Store(), coordinator, SimpleNamespace(entry_id="entry"), entities, added.extend)
    assert old.available is False
    assert len(added) == 1
    assert added[0].unique_id == "entry_rule_new"


@pytest.mark.asyncio
async def test_rule_switch_reads_latest_version_before_saving():
    current = _rule(version=4, name="Editor-Version")

    class Store:
        def __init__(self):
            self.saved = None

        async def async_get(self, rule_id):
            return current

        async def async_save(self, rule, access):
            self.saved = rule
            return rule

    store = Store()
    entity = RuleSwitch(store, object(), SimpleNamespace(entry_id="entry"), _rule(version=1, name="veraltet"))
    entity.async_write_ha_state = lambda: None
    await entity.async_turn_on()
    assert store.saved.version == 5
    assert store.saved.name == "Editor-Version"


@pytest.mark.asyncio
async def test_rule_switch_surfaces_version_conflict_and_protects_critical():
    current = _rule(version=3)

    class Store:
        async def async_get(self, rule_id):
            return current

        async def async_save(self, rule, access):
            raise ValueError("rule version conflict")

    entity = RuleSwitch(Store(), object(), SimpleNamespace(entry_id="entry"), current)
    entity.async_write_ha_state = lambda: None
    with pytest.raises(HomeAssistantError, match="inzwischen geändert"):
        await entity.async_turn_on()
    class CriticalStore(Store):
        async def async_get(self, rule_id):
            return _rule(priority=Priority.CRITICAL)

    critical = RuleSwitch(CriticalStore(), SimpleNamespace(last_update_success=True), SimpleNamespace(entry_id="entry"), _rule(priority=Priority.CRITICAL))
    with pytest.raises(HomeAssistantError, match="Critical"):
        await critical.async_turn_off()
