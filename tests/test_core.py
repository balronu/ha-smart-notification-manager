from dataclasses import replace
from datetime import UTC, datetime, time

import pytest
from smart_notification_manager.core.conditions import TimeWindow, is_in_window
from smart_notification_manager.core.engine import AlarmLifecycleEngine
from smart_notification_manager.core.evaluator import (
    EvaluationContext,
    evaluate_condition,
    evaluate_numeric_trigger,
    evaluate_state_trigger,
)
from smart_notification_manager.core.models import (
    AlarmState,
    ensure_aware,
    new_id,
    validate_id,
)
from smart_notification_manager.core.permissions import Permission, can_access
from smart_notification_manager.core.router import deduplicate_recipients
from smart_notification_manager.core.rules import (
    Comparison,
    ConditionNode,
    TriggerDefinition,
    TriggerKind,
    validate_condition,
    validate_rule,
)


def test_ids_are_opaque_uuid_values():
    assert validate_id(new_id())
    with pytest.raises(ValueError):
        validate_id("not-an-id")


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        ensure_aware(datetime(2026, 1, 1))
    assert ensure_aware(datetime(2026, 1, 1, tzinfo=UTC))


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
    assert is_in_window(window, datetime(2026, 1, 1, 23, tzinfo=UTC))
    assert is_in_window(window, datetime(2026, 1, 1, 6, tzinfo=UTC))
    assert not is_in_window(window, datetime(2026, 1, 1, 12, tzinfo=UTC))


def test_condition_tree_is_deterministic_and_nested():
    tree = ConditionNode(
        "all",
        children=(
            ConditionNode("entity_state", {"entity_id": "binary_sensor.door", "state": "on"}),
            ConditionNode("any", children=(
                ConditionNode("numeric", {"entity_id": "sensor.temp", "comparison": "lt", "threshold": 5}),
                ConditionNode("presence", {"entity_id": "person.michael", "present": True}),
            )),
        ),
    )
    context = EvaluationContext(
        states={"binary_sensor.door": "on"},
        numeric_states={"sensor.temp": 8},
        presence={"person.michael": True},
        now=datetime(2026, 1, 1, 12, tzinfo=UTC),
    )
    assert evaluate_condition(tree, context)


def test_condition_unknown_values_do_not_match():
    condition = ConditionNode("entity_state", {"entity_id": "sensor.x", "state": "on"})
    context = EvaluationContext(states={"sensor.x": "unknown"}, numeric_states={}, presence={}, now=datetime.now(UTC))
    assert not evaluate_condition(condition, context)
    assert not evaluate_state_trigger("unknown", "on", from_state=None, to_state="on")
    assert evaluate_state_trigger("on", "unknown", from_state="on", to_state="unknown", unknown_policy="match")


def test_state_trigger_requires_an_actual_transition():
    assert evaluate_state_trigger("off", "on", from_state="off", to_state="on")
    assert not evaluate_state_trigger("on", "on", from_state="on", to_state="on")
    assert not evaluate_state_trigger("off", "off", from_state="off", to_state="off")
    assert not evaluate_state_trigger("unavailable", "unavailable", from_state=None, to_state=None, unavailable_policy="match")


def test_state_trigger_holds_target_state_then_fires_once():
    started = datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert not evaluate_state_trigger("on", "on", from_state=None, to_state="on", minimum_duration_seconds=120, state_started_at=started, now=started.replace(minute=1, second=59))
    assert evaluate_state_trigger("on", "on", from_state=None, to_state="on", minimum_duration_seconds=120, state_started_at=started, now=started.replace(minute=2))
    assert not evaluate_state_trigger("on", "on", from_state=None, to_state="on", minimum_duration_seconds=120, state_started_at=started, now=started.replace(minute=3), already_triggered=True)


def test_state_trigger_aborts_hold_when_target_state_changes():
    started = datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert not evaluate_state_trigger("on", "off", from_state=None, to_state="on", minimum_duration_seconds=120, state_started_at=started, now=started.replace(minute=3))


def test_presence_requires_a_known_boolean_state():
    present = ConditionNode("presence", {"entity_id": "person.michael", "present": True})
    absent = ConditionNode("presence", {"entity_id": "person.michael", "present": False})
    base = {"states": {}, "numeric_states": {}, "now": datetime.now(UTC)}
    assert evaluate_condition(present, EvaluationContext(presence={"person.michael": True}, **base))
    assert not evaluate_condition(absent, EvaluationContext(presence={"person.michael": True}, **base))
    assert evaluate_condition(absent, EvaluationContext(presence={"person.michael": False}, **base))
    assert not evaluate_condition(absent, EvaluationContext(presence={}, **base))
    assert not evaluate_condition(absent, EvaluationContext(presence={"person.michael": "unknown"}, **base))


def test_numeric_comparison_between():
    condition = ConditionNode("numeric", {"entity_id": "sensor.x", "comparison": Comparison.BETWEEN.value, "threshold": 10, "upper_threshold": 20})
    context = EvaluationContext(states={}, numeric_states={"sensor.x": 15}, presence={}, now=datetime.now(UTC))
    assert evaluate_condition(condition, context)


def test_numeric_trigger_hysteresis_and_minimum_duration():
    assert not evaluate_numeric_trigger(11, "gt", 10, elapsed_seconds=2, minimum_duration_seconds=5)
    assert evaluate_numeric_trigger(9.5, "gt", 10, previous_match=True, hysteresis=1, elapsed_seconds=5)


def test_numeric_range_hysteresis():
    assert evaluate_numeric_trigger(9.5, "between", 10, upper_threshold=20, previous_match=True, hysteresis=1)
    assert not evaluate_numeric_trigger(8.8, "between", 10, upper_threshold=20, previous_match=True, hysteresis=1)


def test_validation_rejects_nonfinite_and_invalid_ranges():
    base = ConditionNode("all", children=(ConditionNode("entity_state", {"entity_id": "binary_sensor.door", "state": "on"}),))
    from smart_notification_manager.core.rules import Priority, RuleDefinition
    now = datetime(2026, 1, 1, tzinfo=UTC)
    rule = RuleDefinition(new_id(), "Test", "", None, None, "Test", Priority.NORMAL, True, (), base, 1, now, now)
    rule = replace(rule, triggers=(TriggerDefinition(TriggerKind.STATE, ("sensor.x",), to_state="on"),))
    with pytest.raises(ValueError, match="finite"):
        validate_rule(replace(rule, triggers=(TriggerDefinition(TriggerKind.NUMERIC, ("sensor.x",), comparison=Comparison.BETWEEN, threshold=float("nan"), upper_threshold=2),)))
    with pytest.raises(ValueError, match="upper threshold"):
        validate_rule(replace(rule, triggers=(TriggerDefinition(TriggerKind.NUMERIC, ("sensor.x",), comparison=Comparison.BETWEEN, threshold=4, upper_threshold=2),)))
    with pytest.raises(ValueError, match="invalid time"):
        validate_condition(ConditionNode("time_window", {"start": "25:00", "end": "07:00"}))
