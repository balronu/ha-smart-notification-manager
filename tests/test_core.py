from datetime import datetime, time, timezone

import pytest

from smart_notification_manager.core.conditions import TimeWindow, is_in_window
from smart_notification_manager.core.engine import AlarmLifecycleEngine
from smart_notification_manager.core.models import AlarmState, ensure_aware, new_id, validate_id
from smart_notification_manager.core.permissions import Permission, can_access
from smart_notification_manager.core.router import deduplicate_recipients


def test_ids_are_opaque_uuid_values():
    assert validate_id(new_id())
    with pytest.raises(ValueError):
        validate_id("not-an-id")


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        ensure_aware(datetime(2026, 1, 1))
    assert ensure_aware(datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_active_alarm_cause_is_unique_until_resolved():
    engine = AlarmLifecycleEngine()
    alarm = engine.start("rule", "sensor:smoke")
    assert alarm.alarm_state is AlarmState.ACTIVE
    with pytest.raises(ValueError, match="already exists"):
        engine.start("rule", "sensor:smoke")
    resolved = engine.resolve("rule", "sensor:smoke", "cleared")
    assert resolved.alarm_state is AlarmState.RESOLVED
    engine.start("rule", "sensor:smoke")


def test_router_removes_only_exact_recipient_duplicates():
    assert deduplicate_recipients(["michael", "michael", "michaela"]).recipient_ids == ("michael", "michaela")


def test_permissions_deny_by_default_and_allow_admin():
    assert not can_access(set(), Permission.TEST)
    assert can_access({Permission.ADMIN.value}, Permission.TEST)


def test_time_window_supports_overnight():
    window = TimeWindow(time(22), time(7))
    assert is_in_window(window, datetime(2026, 1, 1, 23, tzinfo=timezone.utc))
    assert is_in_window(window, datetime(2026, 1, 1, 6, tzinfo=timezone.utc))
    assert not is_in_window(window, datetime(2026, 1, 1, 12, tzinfo=timezone.utc))

