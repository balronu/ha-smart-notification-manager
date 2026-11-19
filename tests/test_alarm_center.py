from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from smart_notification_manager.const import DOMAIN
from smart_notification_manager.core.alarm_center import AlarmCenterStore
from smart_notification_manager.core.alarm_lifecycle import AlarmLifecycleStore, AlarmPolicy
from smart_notification_manager.core.repository import SQLiteRepository
from smart_notification_manager.core.rule_store import EditorAccess, RuleStore
from smart_notification_manager.websocket import _require_alarm_role
from test_storage import valid_storage_rule


@pytest.mark.asyncio
async def test_alarm_center_preserves_ids_filters_paginates_and_returns_timeline(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarm-center.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("admin", frozenset({"edit"})))
    lifecycle = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    first, _ = await lifecycle.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.door", friendly_name="Tür", priority="critical", now=now, category="Sicherheit")
    second, _ = await lifecycle.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.window", friendly_name="Fenster", priority="warning", now=now)
    center = AlarmCenterStore(repository)

    result = await center.async_list_alarms(user_id="admin", role="admin", filters={"critical_only": True}, page=1, page_size=1)
    assert result["total"] == 1
    assert result["alarms"][0]["alarm_id"] == first.alarm_id
    assert result["alarms"][0]["category"] == "Sicherheit"
    assert result["alarms"][0]["status_de"] == "Aktiv"

    detail = await center.async_detail(first.alarm_id, user_id="admin", role="admin")
    assert detail["alarm"]["alarm_id"] == first.alarm_id
    assert [event["event_type"] for event in detail["events"]] == ["triggered"]
    assert (await center.async_list_alarms(user_id="admin", role="admin", filters={"search": second.alarm_id}))["total"] == 1


@pytest.mark.asyncio
async def test_alarm_center_categories_filters_and_personal_ownership(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarm-center.sqlite3")
    center = AlarmCenterStore(repository)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    category = await center.async_save_category({"name": "Wohnmobil"}, user_id="admin", now=now)
    assert category["name"] == "Wohnmobil"
    await center.async_save_role("reader", "read_only", updated_by="admin", now=now)
    saved = await center.async_save_filter({"name": "Meine offenen", "definition": {"open_only": True}, "is_default": True}, user_id="reader", now=now)
    assert saved["user_id"] == "reader" and saved["is_default"]
    assert len(await center.async_list_filters("reader")) == 1
    assert await center.async_list_filters("other") == []
    await center.async_delete_filter(saved["filter_id"], user_id="other")
    assert len(await center.async_list_filters("reader")) == 1
    with pytest.raises(PermissionError, match="anderen Benutzer"):
        await center.async_save_filter({"filter_id": saved["filter_id"], "name": "Fremdänderung", "definition": {}}, user_id="other", now=now)
    assert (await center.async_list_filters("reader"))[0]["name"] == "Meine offenen"
    await center.async_deactivate_category(category["category_id"], user_id="admin", now=now)
    assert await center.async_list_categories() == []


@pytest.mark.asyncio
async def test_alarm_center_non_admin_visibility_is_recipient_scoped(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarm-center.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("admin", frozenset({"edit"})))
    alarm, _ = await AlarmLifecycleStore(repository).async_trigger(
        rule_id=rule.rule_id, entity_id="binary_sensor.door", now=datetime(2026, 1, 1, tzinfo=UTC),
        policy=AlarmPolicy(required_recipient_ids=("reader",)),
    )
    center = AlarmCenterStore(repository)
    await center.async_save_role("reader", "acknowledger", updated_by="admin", now=datetime.now(UTC))
    assert (await center.async_list_alarms(user_id="reader", role="acknowledger"))["total"] == 1
    assert (await center.async_list_alarms(user_id="other", role="read_only"))["total"] == 0
    assert alarm.alarm_id


@pytest.mark.asyncio
async def test_sql_visibility_filter_applies_before_pagination_and_grouping(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarm-center.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("admin", frozenset({"edit"})))
    lifecycle = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    for entity in ("binary_sensor.one", "binary_sensor.two", "binary_sensor.three"):
        await lifecycle.async_trigger(rule_id=rule.rule_id, entity_id=entity, now=now, policy=AlarmPolicy(required_recipient_ids=("reader",)))
    await lifecycle.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.private", now=now, policy=AlarmPolicy(required_recipient_ids=("other",)))
    result = await AlarmCenterStore(repository).async_list_alarms(user_id="reader", role="acknowledger", page=2, page_size=1, group_by="category")
    assert result["total"] == 3
    assert len(result["alarms"]) == 1
    assert sum(result["groups"].values()) == 1


@pytest.mark.asyncio
async def test_legacy_alarm_role_gate_denies_read_only_ack_and_allows_acknowledger(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "roles.sqlite3")
    center = AlarmCenterStore(repository)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    await center.async_save_role("reader", "read_only", updated_by="admin", now=now)
    await center.async_save_role("operator", "acknowledger", updated_by="admin", now=now)

    class Connection:
        def __init__(self, user_id):
            self.user = SimpleNamespace(id=user_id, is_admin=False)
            self.errors = []
            self.results = []

        def send_error(self, *args):
            self.errors.append(args)

        def send_result(self, *args):
            self.results.append(args)

    async def body(_hass, connection, msg):
        connection.send_result(msg["id"], {"ok": True})

    hass = SimpleNamespace(data={DOMAIN: {"alarm_center_store": center}})
    gated = _require_alarm_role("acknowledger")(body)
    reader = Connection("reader")
    await gated(hass, reader, {"id": 1})
    assert reader.errors and not reader.results
    operator = Connection("operator")
    await gated(hass, operator, {"id": 2})
    assert operator.results and not operator.errors
