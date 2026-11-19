from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from smart_notification_manager.core.alarm_lifecycle import AlarmLifecycleStore, AlarmPolicy
from smart_notification_manager.core.models import AlarmState
from smart_notification_manager.core.permissions import Permission
from smart_notification_manager.core.repository import SQLiteRepository
from smart_notification_manager.core.rule_store import EditorAccess, RuleStore
from test_storage import valid_storage_rule


@pytest.mark.asyncio
async def test_two_sensors_create_independent_persistent_alarms(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarms.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({Permission.EDIT.value})))
    store = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)

    first, created_first = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.window_living", friendly_name="Fenster Wohnzimmer", current_state="on", now=now)
    second, created_second = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.window_bedroom", friendly_name="Fenster Schlafzimmer", current_state="on", now=now)
    duplicate, created_duplicate = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.window_living", now=now + timedelta(seconds=1))

    assert created_first and created_second and not created_duplicate
    assert first.alarm_id != second.alarm_id
    assert duplicate.alarm_id == first.alarm_id
    restored = await AlarmLifecycleStore(SQLiteRepository(tmp_path / "alarms.sqlite3")).async_list()
    assert {item.entity_id for item in restored} == {"binary_sensor.window_living", "binary_sensor.window_bedroom"}


@pytest.mark.asyncio
async def test_pending_activation_resolution_and_event_history(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarms.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    store = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    alarm, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.door", now=now, policy=AlarmPolicy(delay_seconds=30))
    assert alarm.alarm_state == AlarmState.PENDING.value
    assert await store.async_activate_pending(now=now + timedelta(seconds=29)) == []
    activated = await store.async_activate_pending(now=now + timedelta(seconds=30))
    assert activated[0].alarm_state == AlarmState.ACTIVE.value
    resolved = await store.async_resolve(alarm.alarm_id, now=now + timedelta(seconds=31))
    assert resolved.alarm_state == AlarmState.RESOLVED.value
    assert [event["event_type"] for event in await store.async_events(alarm.alarm_id)] == ["triggered", "activated", "resolved"]
    with pytest.raises(ValueError, match="already closed"):
        await store.async_resolve(alarm.alarm_id, now=now + timedelta(seconds=32))


@pytest.mark.asyncio
async def test_critical_acknowledgement_and_manual_close_require_confirmation(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarms.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    store = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    alarm, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.smoke", priority="critical", now=now)
    with pytest.raises(PermissionError):
        await store.async_acknowledge(alarm.alarm_id, user_id="owner", now=now, critical_confirmed=False)
    acknowledged = await store.async_acknowledge(alarm.alarm_id, user_id="owner", now=now, scope="recipient-a", critical_confirmed=True)
    assert acknowledged.acknowledgement_state == "acknowledged"
    with pytest.raises(PermissionError):
        await store.async_close(alarm.alarm_id, user_id="owner", now=now, reason="manuell geprüft")
    closed = await store.async_close(alarm.alarm_id, user_id="owner", now=now, reason="manuell geprüft", critical_confirmed=True)
    assert closed.alarm_state == AlarmState.MANUALLY_CLOSED.value


@pytest.mark.asyncio
async def test_overdue_does_not_auto_close_and_stops_repeats_after_resolution(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarms.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    store = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    alarm, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.window", now=now, policy=AlarmPolicy(max_duration_seconds=60, repeat_interval_seconds=10, max_repeats=2))
    overdue = await store.async_mark_overdue(now=now + timedelta(seconds=61))
    assert overdue[0].alarm_state == AlarmState.OVERDUE.value
    assert (await store.async_get(alarm.alarm_id)).alarm_state == AlarmState.OVERDUE.value
    resolved = await store.async_resolve(alarm.alarm_id, now=now + timedelta(seconds=62))
    assert resolved.next_repeat_at is None


@pytest.mark.asyncio
async def test_suppression_repetition_and_escalation_are_persisted_events(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarms.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    store = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    pending, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.pending", now=now, policy=AlarmPolicy(delay_seconds=30))
    assert (await store.async_suppress(pending.alarm_id, now=now, reason="Ruhezeit")).alarm_state == AlarmState.SUPPRESSED.value
    alarm, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.escalate", now=now, policy=AlarmPolicy(repeat_interval_seconds=10, max_repeats=1, escalation_stages=({"after_seconds": 60, "recipient_ids": ["group-b"]},)))
    repeated = await store.async_due_repeats(now=now + timedelta(seconds=10))
    assert repeated[0].repeat_count == 1
    escalated = await store.async_due_escalations(now=now + timedelta(seconds=60))
    assert escalated[0].escalation_level == 1
    assert {event["event_type"] for event in await store.async_events(alarm.alarm_id)} >= {"repeat_due", "escalated"}
