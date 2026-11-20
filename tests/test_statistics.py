from datetime import UTC, datetime
from pathlib import Path

import pytest
from smart_notification_manager.core.adapters import DeliveryRequest
from smart_notification_manager.core.alarm_lifecycle import AlarmLifecycleStore, AlarmPolicy
from smart_notification_manager.core.delivery_store import DeliveryStore
from smart_notification_manager.core.repository import SQLiteRepository
from smart_notification_manager.core.rule_store import EditorAccess, RuleStore
from smart_notification_manager.core.statistics import StatisticsStore, validate_statistics_filters
from test_storage import valid_storage_rule


@pytest.mark.asyncio
async def test_statistics_persist_across_restart_and_cover_alarm_delivery_dimensions(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "statistics.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    alarms = AlarmLifecycleStore(repository)
    now = datetime(2026, 1, 2, 12, tzinfo=UTC)
    alarm, _ = await alarms.async_trigger(
        rule_id=rule.rule_id,
        entity_id="binary_sensor.smoke",
        priority="critical",
        now=now,
        policy=AlarmPolicy(repeat_interval_seconds=10, max_repeats=1),
    )
    await alarms.async_acknowledge(alarm.alarm_id, user_id="owner", now=now, critical_confirmed=True)
    await repository.async_run(
        lambda connection: (
            connection.execute(
                "INSERT INTO recipients(recipient_id, display_name, enabled, metadata_json) VALUES ('owner', 'Owner', 1, '{}')"
            ),
            connection.execute(
                "INSERT INTO channels(channel_id, channel_type, display_name, enabled, config_json) VALUES ('telegram', 'telegram', 'Telegram', 1, '{}')"
            ),
        )
    )
    await DeliveryStore(repository).async_enqueue(
        request=DeliveryRequest("attempt", "owner", "Alarm", "Alarm", {"alarm_id": alarm.alarm_id}),
        idempotency_key="statistics-attempt",
        channel_id="telegram",
        alarm_id=alarm.alarm_id,
        now=now,
    )
    summary = await StatisticsStore(SQLiteRepository(tmp_path / "statistics.sqlite3")).async_summary(priority="critical")
    assert summary["totals"] == {
        "alarms": 1,
        "critical": 1,
        "acknowledged": 1,
        "escalated": 0,
        "repeated": 0,
        "delivery_attempts": 1,
        "delivery_errors": 0,
    }
    assert summary["by_state"] == {"active": 1}
    assert summary["delivery"]["by_channel"] == {"telegram": 1}
    assert summary["daily"]["2026-01-02"]["critical"] == 1
    assert summary["monthly"]["2026-01"]["acknowledged"] == 1


def test_statistics_filters_reject_non_text_values():
    with pytest.raises(ValueError, match="muss Text sein"):
        validate_statistics_filters({"priority": 1})


def test_statistics_filters_accept_frontend_envelope():
    assert validate_statistics_filters({"filters": {"priority": "critical", "state": "active"}}) == {
        "date_from": None,
        "date_to": None,
        "priority": "critical",
        "state": "active",
    }


@pytest.mark.asyncio
async def test_date_to_filter_includes_the_complete_calendar_day(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "statistics.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    alarms = AlarmLifecycleStore(repository)
    await alarms.async_trigger(rule_id=rule.rule_id, entity_id="binary_sensor.door", priority="normal", now=datetime(2026, 1, 2, 23, 59, tzinfo=UTC))
    summary = await StatisticsStore(repository).async_summary(date_from="2026-01-02", date_to="2026-01-02")
    assert summary["totals"]["alarms"] == 1
