from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from smart_notification_manager.core.adapters import DeliveryRequest
from smart_notification_manager.core.alarm_lifecycle import AlarmLifecycleStore, AlarmPolicy
from smart_notification_manager.core.delivery_store import DeliveryStore
from smart_notification_manager.core.models import AlarmState
from smart_notification_manager.core.permissions import Permission
from smart_notification_manager.core.recipient_store import RecipientStore
from smart_notification_manager.core.recipients import Recipient, RecipientDevice
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
    resolved = await store.async_resolve(alarm.alarm_id, now=now + timedelta(seconds=31), actual_state="off", expected_active_state="on")
    assert resolved.alarm_state == AlarmState.RESOLVED.value
    assert [event["event_type"] for event in await store.async_events(alarm.alarm_id)] == ["triggered", "activated", "resolved"]
    with pytest.raises(ValueError, match="already closed"):
        await store.async_resolve(alarm.alarm_id, now=now + timedelta(seconds=32), actual_state="off", expected_active_state="on")


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
    resolved = await store.async_resolve(alarm.alarm_id, now=now + timedelta(seconds=62), actual_state="off", expected_active_state="on")
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


@pytest.mark.asyncio
async def test_pending_revalidation_and_safe_resolution_reject_bad_sensor_states(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarms.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    store = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    normalized, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.normalized", now=now, policy=AlarmPolicy(delay_seconds=1))
    unavailable, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.unavailable", now=now, policy=AlarmPolicy(delay_seconds=1))
    result = await store.async_activate_pending(now=now + timedelta(seconds=1), validations={normalized.alarm_id: False, unavailable.alarm_id: False})
    assert result == []
    assert (await store.async_get(normalized.alarm_id)).alarm_state == AlarmState.SUPPRESSED.value
    active, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.active", now=now, current_state="on")
    with pytest.raises(ValueError, match="still active"):
        await store.async_resolve(active.alarm_id, now=now, actual_state="on", expected_active_state="on")
    with pytest.raises(ValueError, match="safely available"):
        await store.async_resolve(active.alarm_id, now=now, actual_state="unavailable", expected_active_state="on", available=False)


@pytest.mark.asyncio
async def test_zero_repeats_and_restart_do_not_create_repeat_flood(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarms.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    store = AlarmLifecycleStore(repository)
    none, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.none", now=now, policy=AlarmPolicy(repeat_interval_seconds=1, max_repeats=0))
    assert none.next_repeat_at is None
    _scheduled, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.scheduled", now=now, policy=AlarmPolicy(repeat_interval_seconds=1, max_repeats=1))
    restored = AlarmLifecycleStore(SQLiteRepository(tmp_path / "alarms.sqlite3"))
    assert (await restored.async_due_repeats(now=now + timedelta(seconds=1)))[0].repeat_count == 1
    assert await restored.async_due_repeats(now=now + timedelta(seconds=2)) == []


@pytest.mark.asyncio
async def test_bulk_ack_is_atomic_and_parallel_escalation_is_idempotent(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarms.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    store = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    first, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.one", now=now)
    second, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.two", now=now)
    with pytest.raises(ValueError, match="not found"):
        await store.async_acknowledge_many([first.alarm_id, "missing"], user_id="owner", now=now)
    assert (await store.async_get(first.alarm_id)).acknowledgement_state == "unacknowledged"
    assert (await store.async_get(second.alarm_id)).acknowledgement_state == "unacknowledged"
    escalated, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.three", now=now, policy=AlarmPolicy(escalation_stages=({"after_seconds": 1},)))
    results = await __import__("asyncio").gather(store.async_due_escalations(now=now + timedelta(seconds=1)), store.async_due_escalations(now=now + timedelta(seconds=1)))
    assert sum(len(result) for result in results) == 1
    assert len([event for event in await store.async_events(escalated.alarm_id) if event["event_type"] == "escalated"]) == 1


@pytest.mark.asyncio
async def test_closing_alarm_suppresses_pending_delivery_and_allows_linked_retrigger(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "alarms.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    store = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    alarm, _ = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.retrigger", now=now)
    recipients = RecipientStore(repository)
    await recipients.async_save_recipient(Recipient("owner", "Owner", True, (RecipientDevice("phone", "Telefon", "mobile", True, True),)))
    await recipients.async_save_channel({"channel_id": "mobile", "channel_type": "notify", "display_name": "Mobile", "config": {"service": "notify.mobile_app_phone"}})
    delivery = DeliveryStore(repository)
    await delivery.async_enqueue(DeliveryRequest("attempt-retrigger", "owner", "Alarm", "Text", {"alarm_id": alarm.alarm_id}), idempotency_key="alarm-retrigger", channel_id="mobile", alarm_id=alarm.alarm_id)
    closed = await store.async_close(alarm.alarm_id, user_id="owner", now=now, reason="geprüft")
    assert closed.alarm_state == AlarmState.MANUALLY_CLOSED.value
    assert (await delivery.async_list())[0].state == "suppressed"
    linked, created = await store.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.retrigger", now=now + timedelta(seconds=1), parent_alarm_id=alarm.alarm_id)
    assert created and linked.parent_alarm_id == alarm.alarm_id
