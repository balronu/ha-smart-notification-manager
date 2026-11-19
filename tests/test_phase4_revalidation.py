import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from smart_notification_manager.core.alarm_lifecycle import AlarmLifecycleStore, AlarmPolicy
from smart_notification_manager.core.repository import SQLiteRepository
from smart_notification_manager.core.revalidation import (
    async_activate_pending_revalidated,
    revalidate_alarm,
)
from smart_notification_manager.core.rule_store import EditorAccess, RuleStore
from smart_notification_manager.core.rules import (
    ConditionNode,
    Priority,
    RuleDefinition,
    TriggerDefinition,
    TriggerKind,
)
from test_storage import valid_storage_rule


def _hass(states):
    return SimpleNamespace(states=SimpleNamespace(get=lambda entity_id: states.get(entity_id)))


@pytest.mark.asyncio
async def test_pending_revalidation_uses_original_rule_conditions_and_unknown_is_not_normal(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    rule_store = RuleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    rule = RuleDefinition(
        rule_id=valid_storage_rule().rule_id,
        name="Tür",
        description="",
        area_id=None,
        area_name=None,
        category="Sicherheit",
        priority=Priority.WARNING,
        enabled=True,
        triggers=(TriggerDefinition(TriggerKind.STATE, ("binary_sensor.door",), from_state="off", to_state="on", minimum_duration_seconds=5),),
        conditions=ConditionNode("all", children=(ConditionNode("presence", {"entity_id": "person.michael", "present": True}),)),
        version=1,
        created_at=now,
        updated_at=now,
    )
    await rule_store.async_save(rule, EditorAccess("owner", frozenset({"edit"})))
    alarm_store = AlarmLifecycleStore(repository)
    alarm, _ = await alarm_store.async_trigger(
        rule_id=rule.rule_id,
        rule_version=1,
        entity_id="binary_sensor.door",
        previous_state="off",
        current_state="on",
        now=now,
        policy=AlarmPolicy(delay_seconds=1),
    )
    states = {
        "binary_sensor.door": SimpleNamespace(state="on", last_changed=now - timedelta(seconds=10)),
        "person.michael": SimpleNamespace(state="not_home", last_changed=now),
    }
    result = revalidate_alarm(_hass(states), rule, alarm, now + timedelta(seconds=1))
    assert not result.valid and result.safe_to_resolve
    states["person.michael"] = SimpleNamespace(state="unknown", last_changed=now)
    result = revalidate_alarm(_hass(states), rule, alarm, now + timedelta(seconds=1))
    assert not result.valid and not result.safe_to_resolve

    pending, _ = await alarm_store.async_trigger(
        rule_id=rule.rule_id,
        rule_version=1,
        entity_id="binary_sensor.pending",
        previous_state="off",
        current_state="on",
        now=now,
        policy=AlarmPolicy(delay_seconds=1),
    )
    states["binary_sensor.pending"] = SimpleNamespace(state="unavailable", last_changed=now)
    assert await async_activate_pending_revalidated(_hass(states), alarm_store, rule_store, now + timedelta(seconds=1)) == []
    assert (await alarm_store.async_get(pending.alarm_id)).alarm_state == "suppressed"


@pytest.mark.asyncio
async def test_all_required_acknowledgement_is_persistent_and_stops_escalation(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    store = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    alarm, _ = await store.async_trigger(
        rule_id=rule.rule_id,
        entity_id="binary_sensor.door",
        now=now,
        policy=AlarmPolicy(
            acknowledgement_mode="all_required",
            required_recipient_ids=("michael", "anna"),
            escalation_stages=({"after_seconds": 1},),
        ),
    )
    with pytest.raises(PermissionError, match="required recipient"):
        await store.async_acknowledge(alarm.alarm_id, user_id="outsider", now=now)
    partial = await store.async_acknowledge(alarm.alarm_id, user_id="michael", now=now)
    assert partial.acknowledgement_state == "partially_acknowledged"
    assert await store.async_due_escalations(now=now + timedelta(seconds=1))
    complete = await store.async_acknowledge(alarm.alarm_id, user_id="anna", now=now + timedelta(seconds=2))
    assert complete.acknowledgement_state == "acknowledged"
    restored = await AlarmLifecycleStore(SQLiteRepository(tmp_path / "manager.sqlite3")).async_get(alarm.alarm_id)
    assert restored.required_recipient_ids == ("anna", "michael")
    assert await store.async_due_escalations(now=now + timedelta(seconds=3)) == []


@pytest.mark.asyncio
async def test_parallel_last_ack_and_escalation_leave_one_complete_ack_state(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    store = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    alarm, _ = await store.async_trigger(
        rule_id=rule.rule_id,
        entity_id="binary_sensor.parallel",
        now=now,
        policy=AlarmPolicy(
            acknowledgement_mode="all_required",
            required_recipient_ids=("michael", "anna"),
            escalation_stages=({"after_seconds": 1},),
        ),
    )
    await store.async_acknowledge(alarm.alarm_id, user_id="michael", now=now)
    await asyncio.gather(
        store.async_acknowledge(alarm.alarm_id, user_id="anna", now=now + timedelta(seconds=1)),
        store.async_due_escalations(now=now + timedelta(seconds=1)),
    )
    assert (await store.async_get(alarm.alarm_id)).acknowledgement_state == "acknowledged"
    assert await store.async_due_escalations(now=now + timedelta(seconds=2)) == []
