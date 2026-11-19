import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from smart_notification_manager.core.alarm_lifecycle import AlarmLifecycleStore, AlarmPolicy
from smart_notification_manager.core.delivery_store import DeliveryStore
from smart_notification_manager.core.policies import PolicyStore, QuietHours
from smart_notification_manager.core.repeat_delivery import RepeatEscalationDeliveryPlanner
from smart_notification_manager.core.repository import SQLiteRepository

NOW = datetime(2026, 1, 1, 12, tzinfo=UTC)


async def seed_rule(repository):
    def operation(connection):
        connection.execute("INSERT OR IGNORE INTO recipients(recipient_id,display_name,enabled,metadata_json) VALUES (?,?,?,?)", ("person", "Person", 1, "{}"))
        connection.execute("INSERT OR IGNORE INTO recipients(recipient_id,display_name,enabled,metadata_json) VALUES (?,?,?,?)", ("owner", "Eigentümer", 1, "{}"))
        connection.execute("INSERT OR IGNORE INTO recipients(recipient_id,display_name,enabled,metadata_json) VALUES (?,?,?,?)", ("oncall", "Bereitschaft", 1, "{}"))
        connection.execute("INSERT OR IGNORE INTO channels(channel_id,channel_type,display_name,enabled,config_json) VALUES (?,?,?,?,?)", ("mobile", "mobile_app", "Mobil", 1, "{}"))
        connection.execute("INSERT OR IGNORE INTO channels(channel_id,channel_type,display_name,enabled,config_json) VALUES (?,?,?,?,?)", ("sms", "sms", "SMS", 1, "{}"))
        connection.execute("INSERT INTO rules(rule_id,name,category,enabled,created_at,updated_at,description,area_id,area_name,priority,deleted_at) VALUES (?,?,?,?,?,?,?,?,?,?,NULL)", ("rule", "Regel", "Test", 1, NOW.isoformat(), NOW.isoformat(), "", None, None, "normal"))
    await repository.async_run(operation)


@pytest.mark.asyncio
async def test_gate24_repeat_plans_policy_gated_idempotent_delivery_without_adapter(tmp_path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    await seed_rule(repository)
    alarm_store = AlarmLifecycleStore(repository)
    alarm, _ = await alarm_store.async_trigger(rule_id="rule", entity_id="sensor.door", friendly_name="Tür", now=NOW, policy=AlarmPolicy(repeat_interval_seconds=10, max_repeats=2, repeat_recipient_ids=("person",), repeat_channel_ids=("mobile",)))
    planner = RepeatEscalationDeliveryPlanner(alarm_store, DeliveryStore(repository), PolicyStore(repository))
    result = await planner.async_plan_due(now=NOW + timedelta(seconds=10))
    assert result["planned"][0]["alarm_id"] == alarm.alarm_id
    assert result["planned"][0]["adapter_called"] is False
    duplicate = await planner.async_plan_due(now=NOW + timedelta(seconds=10))
    assert duplicate == {"planned": [], "suppressed": []}
    assert await repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM delivery_attempts").fetchone()[0]) == 1


@pytest.mark.asyncio
async def test_gate24_escalation_switches_routing_and_acknowledgement_stops_future_stage(tmp_path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    await seed_rule(repository)
    alarms = AlarmLifecycleStore(repository)
    alarm, _ = await alarms.async_trigger(rule_id="rule", entity_id="sensor.smoke", now=NOW, policy=AlarmPolicy(escalation_stages=({"after_seconds": 1, "recipient_ids": ["oncall"], "channel_ids": ["sms"]},), repeat_recipient_ids=("owner",), repeat_channel_ids=("mobile",)))
    planner = RepeatEscalationDeliveryPlanner(alarms, DeliveryStore(repository), PolicyStore(repository))
    result = await planner.async_plan_due(now=NOW + timedelta(seconds=1))
    assert result["planned"][0]["recipient_id"] == "oncall"
    await alarms.async_acknowledge(alarm.alarm_id, user_id="owner", now=NOW + timedelta(seconds=2))
    assert await alarms.async_due_escalations(now=NOW + timedelta(seconds=3)) == []


@pytest.mark.asyncio
async def test_gate24_quiet_hours_suppress_repeat_without_reserving_delivery(tmp_path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    alarms = AlarmLifecycleStore(repository)
    await seed_rule(repository)
    _alarm, _ = await alarms.async_trigger(rule_id="rule", entity_id="sensor.window", now=NOW, policy=AlarmPolicy(repeat_interval_seconds=10, max_repeats=1, repeat_recipient_ids=("owner",), repeat_channel_ids=("mobile",)))
    policies = PolicyStore(repository)
    await policies.async_save_quiet_hours(QuietHours("night", "Nacht", True, tuple(range(7)), "00:00", "23:59"), user_id="owner", now=NOW)
    result = await RepeatEscalationDeliveryPlanner(alarms, DeliveryStore(repository), policies).async_plan_due(now=NOW + timedelta(seconds=10))
    assert result["planned"] == []
    assert result["suppressed"][0]["reason"] == "quiet_hours"
    assert await repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM delivery_attempts").fetchone()[0]) == 0


@pytest.mark.asyncio
async def test_gate24_parallel_planners_do_not_duplicate_delivery_jobs(tmp_path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    await seed_rule(repository)
    alarms = AlarmLifecycleStore(repository)
    await alarms.async_trigger(rule_id="rule", entity_id="sensor.door", now=NOW, policy=AlarmPolicy(repeat_interval_seconds=1, max_repeats=1, repeat_recipient_ids=("owner",), repeat_channel_ids=("mobile",)))
    def planner():
        return RepeatEscalationDeliveryPlanner(alarms, DeliveryStore(repository), PolicyStore(repository))
    results = await asyncio.gather(*(planner().async_plan_due(now=NOW + timedelta(seconds=1)) for _ in range(2)))
    assert sum(len(item["planned"]) for item in results) == 1
    assert await repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM delivery_attempts").fetchone()[0]) == 1
