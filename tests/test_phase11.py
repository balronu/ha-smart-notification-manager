from datetime import UTC, datetime
from pathlib import Path

import pytest
from smart_notification_manager.core.automation_migration import AutomationMigrationStore
from smart_notification_manager.core.repository import SQLiteRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)
ROOT = Path(__file__).parents[1]


def automation():
    return {"id": "phase11", "alias": "Tür", "trigger": {"platform": "state", "entity_id": "binary_sensor.tuer", "to": "on"}, "action": [{"service": "notify.mobile_app_phone", "data": {"message": "Tür offen"}}]}


def nested_automation():
    return {
        "id": "nested-phase12",
        "alias": "Keller",
        "trigger": [{"platform": "state", "entity_id": "binary_sensor.keller", "to": "on"}],
        "condition": [{"condition": "state", "entity_id": "input_boolean.away", "state": "on"}],
        "action": [
            {"variables": {"sec" + "ret": "fixture-value"}},
            {"choose": [{"conditions": [], "sequence": [{"service": "notify.mobile_app_phone", "data": {"message": "Keller offen"}}]}]},
            {"repeat": {"count": 2, "sequence": [{"service": "notify.mobile_app_tablet", "data": {"message": "Wiederholung"}}]}},
            {"service": "light.turn_on", "target": {"entity_id": "light.keller"}},
        ],
    }


@pytest.mark.asyncio
async def test_phase11_export_import_roundtrip_creates_new_unapproved_plan(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    original = await store.async_prepare(automation(), user_id="admin", now=NOW)
    exported = await store.async_export_plan(original["plan_id"], user_id="admin")
    imported = await store.async_import_plan(exported, user_id="admin", confirm=True, now=NOW)
    assert exported["format"] == "smart_notification_manager.phase11"
    assert imported["plan_id"] != original["plan_id"]
    assert imported["requires_confirmation"] is True
    assert imported["ha_write_performed"] is False


@pytest.mark.asyncio
async def test_phase11_import_requires_confirmation(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    plan = await store.async_prepare(automation(), user_id="admin", now=NOW)
    payload = await store.async_export_plan(plan["plan_id"], user_id="admin")
    with pytest.raises(PermissionError):
        await store.async_import_plan(payload, user_id="admin", confirm=False, now=NOW)


@pytest.mark.asyncio
async def test_phase11_backup_restore_is_atomic_and_conflict_checked(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    plan = await store.async_prepare(automation(), user_id="admin", now=NOW)
    backup = await store.async_create_backup(plan["plan_id"], user_id="admin", now=NOW)
    with pytest.raises(ValueError, match="Quellversion"):
        await store.async_restore_backup(backup["backup_id"], user_id="admin", expected_source_hash="stale", now=NOW)
    restored = await store.async_restore_backup(backup["backup_id"], user_id="admin", expected_source_hash=backup["source_hash"], now=NOW)
    assert restored["status"] == "prepared"
    assert restored["ha_write_performed"] is False


@pytest.mark.asyncio
async def test_phase11_recovery_snapshot_survives_new_store_and_has_no_delivery_rows(tmp_path):
    path = tmp_path / "manager.sqlite3"
    first = AutomationMigrationStore(SQLiteRepository(path))
    plan = await first.async_prepare(automation(), user_id="admin", now=NOW)
    await first.async_reference_event(automation_id="phase11", execution_ref="run-1", entity_id="binary_sensor.tuer", rule_id=None, event="open", now=NOW)
    second = AutomationMigrationStore(SQLiteRepository(path))
    recovery = await second.async_recovery_snapshot(user_id="admin")
    assert any(item["plan_id"] == plan["plan_id"] for item in recovery["plans"])
    assert recovery["external_references"][0]["execution_ref"] == "run-1"
    assert await second.repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM alarm_instances").fetchone()[0]) == 0
    assert recovery["ha_write_performed"] is False


@pytest.mark.asyncio
async def test_phase12_nested_hybrid_replaces_only_selected_actions_and_preserves_control_flow(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    plan = await store.async_prepare(nested_automation(), user_id="admin", now=NOW)
    assert plan["classification"] == "hybrid_migrierbar"
    hybrid = plan["draft"]
    assert hybrid["classification"] == "hybrid_migrierbar"
    assert hybrid["transformed"]["action"][1]["choose"][0]["sequence"][0]["service"] == "smart_notification_manager.send"
    assert hybrid["transformed"]["action"][2]["repeat"]["sequence"][0]["service"] == "smart_notification_manager.send"
    assert hybrid["transformed"]["action"][3]["service"] == "light.turn_on"
    assert hybrid["no_automatic_activation"] is True


@pytest.mark.asyncio
async def test_phase12_external_reference_is_idempotent_and_has_monotonic_lifecycle(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    first = await store.async_reference_event(automation_id="nested-phase12", execution_ref="run-1", entity_id="binary_sensor.keller", rule_id=None, event="open", now=NOW)
    duplicate = await store.async_reference_event(automation_id="nested-phase12", execution_ref="run-1", entity_id="binary_sensor.keller", rule_id=None, event="open", now=NOW)
    assert duplicate["reference_id"] == first["reference_id"]
    assert duplicate["alarm_id"] == first["alarm_id"]
    acknowledged = await store.async_reference_event(automation_id="nested-phase12", execution_ref="run-1", entity_id="binary_sensor.keller", rule_id=None, event="acknowledge", now=NOW)
    assert acknowledged["alarm_status"] == "acknowledged"
    resolved = await store.async_reference_event(automation_id="nested-phase12", execution_ref="run-1", entity_id="binary_sensor.keller", rule_id=None, event="resolve", now=NOW)
    assert resolved["alarm_status"] == "resolved"
    with pytest.raises(ValueError, match="nicht erneut geöffnet"):
        await store.async_reference_event(automation_id="nested-phase12", execution_ref="run-1", entity_id="binary_sensor.keller", rule_id=None, event="open", now=NOW)
    with pytest.raises(ValueError, match="anderen Entität"):
        await store.async_reference_event(automation_id="nested-phase12", execution_ref="run-1", entity_id="binary_sensor.other", rule_id=None, event="update", now=NOW)


@pytest.mark.asyncio
async def test_phase12_migration_export_redacts_nested_secrets(tmp_path):
    store = AutomationMigrationStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    plan = await store.async_prepare(nested_automation(), user_id="admin", now=NOW)
    exported = await store.async_export_plan(plan["plan_id"], user_id="admin")
    serialized = str(exported)
    assert "fixture-value" not in serialized
    assert "[ausgeblendet]" in serialized


def test_phase11_frontend_is_german_read_only_and_mirrored():
    source = (ROOT / "frontend/phase-11-guided-migration.js").read_text()
    assert source == (ROOT / "custom_components/smart_notification_manager/frontend/phase-11-guided-migration.js").read_text()
    assert "phase11/${action}" in source and 'data-action="recovery"' in source and 'data-action="export"' in source and 'data-action="import"' in source and 'data-action="backup"' in source
    assert "keine HA-Automation" in source


def test_phase11_fixture_documents_responsive_viewports():
    fixture = (ROOT / "frontend/phase-11-guided-migration-fixture.html").read_text()
    assert 'data-viewport="desktop"' in fixture
    assert 'data-viewport="ipad"' in fixture
    assert 'data-viewport="iphone"' in fixture
    assert "keine Home-Assistant-Automation" in fixture
