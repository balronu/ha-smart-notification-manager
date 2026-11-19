from dataclasses import replace
from datetime import UTC, datetime

import pytest
from smart_notification_manager.core.models import new_id
from smart_notification_manager.core.rules import (
    ConditionNode,
    Priority,
    RuleDefinition,
    TriggerDefinition,
    TriggerKind,
    validate_rule,
)


def valid_rule():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return RuleDefinition(
        rule_id=new_id(),
        name="Tür offen",
        description="",
        area_id="flur",
        area_name="Flur",
        category="Sicherheit",
        priority=Priority.WARNING,
        enabled=True,
        triggers=(TriggerDefinition(kind=TriggerKind.STATE, entity_ids=("binary_sensor.door",), to_state="on"),),
        conditions=ConditionNode("all", children=(ConditionNode("entity_state", {"entity_id": "binary_sensor.door", "state": "on"}),)),
        version=1,
        created_at=now,
        updated_at=now,
    )


def test_rule_validation_rejects_missing_trigger():
    rule = valid_rule()
    invalid = replace(rule, triggers=())
    with pytest.raises(ValueError, match="at least one trigger"):
        validate_rule(invalid)


def test_rule_validation_accepts_state_rule():
    validate_rule(valid_rule())
