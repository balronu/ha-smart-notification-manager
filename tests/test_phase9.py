import asyncio
import copy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from smart_notification_manager.core.automation_migration import (
    AutomationMigrationStore,
    build_full_migration_draft,
    build_hybrid_plan,
    discover_automation,
)
from smart_notification_manager.core.repository import SQLiteRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)
ROOT = Path(__file__).parents[1]


def simple(service="notify.mobile_app_phone"):
    return {
        "id": "window_warning",
        "alias": "Fensterwarnung",
        "enabled": True,
        "trigger": {"platform": "state", "entity_id": "binary_sensor.door", "from": "off", "to": "on"},
        "condition": [{"condition": "state", "entity_id": "binary_sensor.door", "state": "on"}],
        "action": [{"service": service, "data": {"message": "Tür offen"}}],
    }


def nested():
    value = simple()
    value["action"] = [{"service": "light.turn_on", "target": {"entity_id": "light.door"}}, {"choose": [{"conditions": [], "sequence": [{"service": "notify.mobile_app_phone", "data": {"message": "Tür offen"}}]}]}]
    return value


def test_simple_notify_automation_is_discovered():
    result = discover_automation(simple())
    assert result["notification_count"] == 1
    assert result["channels"] == ["mobile_app_phone"]
    assert result["classification"] == "vollständig_migrierbar"
    assert result["action_positions"] == ["0"]


def test_multiple_notify_actions_and_positions_are_reported():
    value = simple()
    value["action"].append({"service": "notify.telegram", "data": {"message": "Auch Telegram"}})
    result = discover_automation(value)
    assert result["notification_count"] == 2
    assert result["channels"] == ["mobile_app_phone", "telegram"]
    assert result["action_positions"] == ["0", "1"]


def test_nested_choose_if_and_repeat_are_found():
    value = nested()
    value["action"].append({"if": [{"condition": "state"}], "then": [{"service": "tts.speak", "data": {"message": "Alarm"}}]})
    value["action"].append({"repeat": {"count": 2, "sequence": [{"service": "notify.send_message", "data": {"message": "Wiederholung"}}]}})
    result = discover_automation(value)
    assert result["notification_count"] == 3
    assert result["classification"] == "hybrid_migrierbar"
    assert any("Verschachtelte" in risk for risk in result["risks"])


def test_dynamic_service_is_never_safe():
    result = discover_automation({**simple("{{ notification_service }}"), "action": [{"action": "{{ notification_service }}"}]})
    assert result["classification"] == "nur_manuell"
    assert result["migration_capable"] is False


def test_unsupported_automation_is_rejected():
    result = discover_automation({"id": "scene", "alias": "Licht", "trigger": {"platform": "state"}, "action": [{"service": "light.turn_on"}]})
    assert result["classification"] == "nicht_unterstützt"
    assert result["notification_count"] == 0


def test_security_automation_needs_explicit_manual_approval():
    result = discover_automation({**simple(), "id": "security_alarm"})
    assert result["classification"] == "nur_manuell"
    assert any("Sicherheits" in risk for risk in result["risks"])


def test_full_migration_draft_is_disabled_and_observational():
    source = simple()
    before = copy.deepcopy(source)
    draft = build_full_migration_draft(source, available_entities={"binary_sensor.door"}, recipient_ids=["michael"])
    assert draft["enabled"] is False
    assert draft["observation_mode"] is True
    assert draft["routing"] == {"recipient_ids": ["michael"], "channel_ids": ["mobile_app_phone"]}
    assert draft["missing_entities"] == []
    assert source == before


def test_missing_entities_are_visible_in_draft():
    draft = build_full_migration_draft(simple(), available_entities=set())
    assert draft["missing_entities"] == ["binary_sensor.door"]


def test_hybrid_replaces_only_selected_notify_and_preserves_other_actions():
    source = nested()
    plan = build_hybrid_plan(source, selected_paths={("1", "choose[0]", "sequence", "0")}, external_alarm_reference="run-1")
    transformed = plan["transformed"]
    assert transformed["action"][0]["service"] == "light.turn_on"
    assert transformed["action"][1]["choose"][0]["sequence"][0]["service"] == "smart_notification_manager.send"
    assert transformed["action"][1]["choose"][0]["sequence"][0]["data"]["external_alarm_reference"] == "run-1"
    assert source["action"][1]["choose"][0]["sequence"][0]["service"].startswith("notify.")


def test_hybrid_plan_contains_preview_differences_and_rollback():
    plan = build_hybrid_plan(simple())
    assert plan["preserved_features"]
    assert plan["non_transferable"]
    assert plan["no_automatic_activation"] is True
    assert plan["original"]["action"][0]["service"] == "notify.mobile_app_phone"


@pytest.mark.asyncio
async def test_prepare_persists_snapshot_without_changing_source(tmp_path):
    source = simple()
    before = copy.deepcopy(source)
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    plan = await store.async_prepare(source, user_id="admin", available_entities={"binary_sensor.door"}, now=NOW)
    assert plan["status"] == "prepared"
    assert plan["original"] == before
    assert source == before


@pytest.mark.asyncio
async def test_activation_without_confirmation_is_rejected(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    plan = await store.async_prepare(simple(), user_id="admin", now=NOW)
    with pytest.raises(PermissionError):
        await store.async_activate(plan["plan_id"], simple(), user_id="admin", confirm=False, now=NOW)


@pytest.mark.asyncio
async def test_activation_rechecks_automation_hash_and_is_non_mutating(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    source = simple()
    plan = await store.async_prepare(source, user_id="admin", now=NOW)
    changed = {**source, "alias": "Geändert"}
    with pytest.raises(ValueError, match="geändert"):
        await store.async_activate(plan["plan_id"], changed, user_id="admin", confirm=True, now=NOW)
    approved = await store.async_activate(plan["plan_id"], source, user_id="admin", confirm=True, now=NOW)
    assert approved["ha_write_performed"] is False
    assert approved["requires_isolated_fixture"] is True


@pytest.mark.asyncio
async def test_rollback_is_available_after_prepare(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    plan = await store.async_prepare(simple(), user_id="admin", now=NOW)
    result = await store.async_rollback(plan["plan_id"], user_id="admin", now=NOW)
    assert result["status"] == "rolled_back"


@pytest.mark.asyncio
async def test_external_reference_open_is_idempotent(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    first = await store.async_reference_event(automation_id="auto", execution_ref="run", entity_id="binary_sensor.door", rule_id="rule", event="open", now=NOW)
    second = await store.async_reference_event(automation_id="auto", execution_ref="run", entity_id="binary_sensor.door", rule_id="rule", event="open", now=NOW)
    assert first["alarm_id"] == second["alarm_id"]
    count = await store.repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM external_alarm_references").fetchone()[0])
    assert count == 1


@pytest.mark.asyncio
async def test_external_reference_update_ack_and_resolve_keep_same_alarm(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    opened = await store.async_reference_event(automation_id="auto", execution_ref="run", entity_id="binary_sensor.door", rule_id="rule", event="open", now=NOW)
    updated = await store.async_reference_event(automation_id="auto", execution_ref="run", entity_id="binary_sensor.door", rule_id="rule", event="update", now=NOW)
    acknowledged = await store.async_reference_event(automation_id="auto", execution_ref="run", entity_id="binary_sensor.door", rule_id="rule", event="acknowledge", now=NOW)
    resolved = await store.async_reference_event(automation_id="auto", execution_ref="run", entity_id="binary_sensor.door", rule_id="rule", event="resolve", now=NOW)
    assert {item["alarm_id"] for item in (opened, updated, acknowledged, resolved)} == {opened["alarm_id"]}
    assert resolved["alarm_status"] == "resolved"


@pytest.mark.asyncio
async def test_unknown_execution_cannot_resolve_other_alarm(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    with pytest.raises(ValueError):
        await store.async_reference_event(automation_id="auto", execution_ref="missing", entity_id="binary_sensor.door", rule_id="rule", event="resolve", now=NOW)


@pytest.mark.asyncio
async def test_reference_survives_new_store_instance(tmp_path):
    path = tmp_path / "manager.sqlite3"
    first = AutomationMigrationStore(SQLiteRepository(path))
    saved = await first.async_reference_event(automation_id="auto", execution_ref="restart", entity_id="sensor.x", rule_id="rule", event="open", now=NOW)
    second = AutomationMigrationStore(SQLiteRepository(path))
    loaded = await second.async_get_reference("auto", "restart")
    assert loaded["alarm_id"] == saved["alarm_id"]


def test_tts_and_persistent_notifications_are_detected():
    value = simple()
    value["action"] = [{"service": "persistent_notification.create", "data": {"message": "Hinweis"}}, {"service": "tts.cloud_say", "data": {"message": "Sprich"}}]
    result = discover_automation(value)
    assert [item["kind"] for item in result["notification_actions"]] == ["Persistente Benachrichtigung", "TTS"]


def test_secret_values_are_not_in_preview():
    value = simple()
    value["action"][0]["data"]["token"] = "super-secret"
    result = discover_automation(value)
    assert "super-secret" not in str(result)
    assert "ausgeblendet" in str(result)


def test_dynamic_nested_unknown_is_not_simplified():
    value = nested()
    value["action"][1]["choose"][0]["sequence"].append({"service": "{{ states('sensor.dynamic') }}"})
    result = discover_automation(value)
    assert result["classification"] == "nur_manuell"


@pytest.mark.asyncio
async def test_observation_preparation_creates_no_delivery_or_alarm_rows(tmp_path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    store = AutomationMigrationStore(repository)
    await store.async_prepare(simple(), user_id="admin", now=NOW)
    assert await repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM delivery_attempts").fetchone()[0]) == 0
    assert await repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM alarm_instances").fetchone()[0]) == 0


@pytest.mark.asyncio
async def test_parallel_reference_open_calls_have_one_mapping(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    results = await asyncio.gather(*[store.async_reference_event(automation_id="auto", execution_ref="parallel", entity_id="sensor.x", rule_id="rule", event="open", now=NOW) for _ in range(2)])
    assert results[0]["alarm_id"] == results[1]["alarm_id"]


def test_preview_has_no_automatic_activation_marker():
    result = build_hybrid_plan(simple())
    assert result["no_automatic_activation"] is True


def test_phase9_frontend_exposes_prepare_activate_and_rollback_without_ha_write():
    source = (ROOT / "frontend/phase-9-automation-migration.js").read_text()
    assert source == (ROOT / "custom_components/smart_notification_manager/frontend/phase-9-automation-migration.js").read_text()
    assert 'phase9/prepare' in source
    assert 'phase9/activate' in source
    assert 'phase9/rollback' in source
    assert "ha_write_performed" in source


def test_original_automation_hash_changes_on_concurrent_edit():
    original = discover_automation(simple())
    changed = simple()
    changed["action"][0]["data"]["message"] = "anders"
    assert original["source_hash"] != discover_automation(changed)["source_hash"]
