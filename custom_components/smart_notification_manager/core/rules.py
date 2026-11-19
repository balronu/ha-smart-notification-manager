"""Validated rule and condition contracts for the graphical editor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from .models import ensure_aware, new_id, validate_id


class Priority(StrEnum):
    INFO = "info"
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class TriggerKind(StrEnum):
    STATE = "state"
    NUMERIC = "numeric"


class Comparison(StrEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    BETWEEN = "between"


class UnknownPolicy(StrEnum):
    IGNORE = "ignore"
    MATCH = "match"


@dataclass(frozen=True, slots=True)
class EntitySnapshot:
    """Read-only entity metadata shown by the editor."""

    entity_id: str
    friendly_name: str
    area_id: str | None = None
    area_name: str | None = None
    entity_type: str = "unknown"
    state: str | None = None


@dataclass(frozen=True, slots=True)
class TriggerDefinition:
    kind: TriggerKind
    entity_ids: tuple[str, ...]
    from_state: str | None = None
    to_state: str | None = None
    comparison: Comparison | None = None
    threshold: float | None = None
    upper_threshold: float | None = None
    hysteresis: float | None = None
    minimum_duration_seconds: int = 0
    delay_seconds: int = 0
    unknown_policy: UnknownPolicy = UnknownPolicy.IGNORE
    unavailable_policy: UnknownPolicy = UnknownPolicy.IGNORE


@dataclass(frozen=True, slots=True)
class ConditionNode:
    """Recursive condition tree; children are serialized as dictionaries."""

    kind: str
    value: Any = None
    children: tuple[ConditionNode, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RuleDefinition:
    rule_id: str
    name: str
    description: str
    area_id: str | None
    area_name: str | None
    category: str
    priority: Priority
    enabled: bool
    triggers: tuple[TriggerDefinition, ...]
    conditions: ConditionNode
    version: int
    created_at: datetime
    updated_at: datetime


def new_rule(name: str, *, now: datetime, category: str = "Sonstiges") -> RuleDefinition:
    """Create a valid empty rule draft for the visual editor."""

    ensure_aware(now)
    return RuleDefinition(
        rule_id=new_id(),
        name=name.strip(),
        description="",
        area_id=None,
        area_name=None,
        category=category.strip() or "Sonstiges",
        priority=Priority.NORMAL,
        enabled=True,
        triggers=(),
        conditions=ConditionNode("all", children=()),
        version=1,
        created_at=now,
        updated_at=now,
    )


def validate_rule(rule: RuleDefinition) -> None:
    """Validate all fields before a rule can reach persistence."""

    validate_id(rule.rule_id)
    if not rule.name.strip():
        raise ValueError("rule name must not be empty")
    if not rule.category.strip():
        raise ValueError("rule category must not be empty")
    if rule.version < 1:
        raise ValueError("rule version must be positive")
    ensure_aware(rule.created_at)
    ensure_aware(rule.updated_at)
    if not rule.triggers:
        raise ValueError("at least one trigger is required")
    for trigger in rule.triggers:
        _validate_trigger(trigger)
    validate_condition(rule.conditions)


def _validate_trigger(trigger: TriggerDefinition) -> None:
    if not trigger.entity_ids:
        raise ValueError("trigger needs at least one entity")
    if any(not entity_id.startswith(("binary_sensor.", "input_", "sensor.", "switch.", "device_tracker.")) for entity_id in trigger.entity_ids):
        raise ValueError("trigger contains an invalid entity id")
    if trigger.minimum_duration_seconds < 0 or trigger.delay_seconds < 0:
        raise ValueError("durations must not be negative")
    if trigger.kind is TriggerKind.STATE and not (trigger.from_state or trigger.to_state):
        raise ValueError("state trigger needs a source or target state")
    if trigger.kind is TriggerKind.NUMERIC:
        if trigger.comparison is None or trigger.threshold is None:
            raise ValueError("numeric trigger needs a comparison and threshold")
        if trigger.comparison is Comparison.BETWEEN and trigger.upper_threshold is None:
            raise ValueError("between trigger needs an upper threshold")
        if trigger.hysteresis is not None and trigger.hysteresis < 0:
            raise ValueError("hysteresis must not be negative")


def validate_condition(node: ConditionNode) -> None:
    """Validate a condition tree independently from the frontend."""

    if node.kind in {"all", "any"}:
        if not node.children:
            raise ValueError("condition groups must contain a condition")
        for child in node.children:
            validate_condition(child)
        return
    if node.kind == "entity_state":
        if not isinstance(node.value, dict) or not node.value.get("entity_id"):
            raise ValueError("entity state condition needs an entity")
        return
    if node.kind == "numeric":
        if not isinstance(node.value, dict) or not node.value.get("entity_id"):
            raise ValueError("numeric condition needs an entity")
        if node.value.get("comparison") not in {item.value for item in Comparison}:
            raise ValueError("numeric condition has an invalid comparison")
        return
    if node.kind == "presence":
        if not isinstance(node.value, dict) or not node.value.get("entity_id"):
            raise ValueError("presence condition needs an entity")
        return
    if node.kind == "weekday":
        if not isinstance(node.value, dict) or not node.value.get("days"):
            raise ValueError("weekday condition needs a day")
        return
    if node.kind == "time_window":
        if not isinstance(node.value, dict) or not node.value.get("start") or not node.value.get("end"):
            raise ValueError("time window needs start and end")
        return
    raise ValueError(f"unknown condition kind: {node.kind}")


def condition_to_dict(node: ConditionNode) -> dict[str, Any]:
    """Serialize a tree for versioned storage and the frontend contract."""

    return {
        "kind": node.kind,
        "value": node.value,
        "children": [condition_to_dict(child) for child in node.children],
    }


def trigger_to_dict(trigger: TriggerDefinition) -> dict[str, Any]:
    value = asdict(trigger)
    value["kind"] = trigger.kind.value
    value["comparison"] = trigger.comparison.value if trigger.comparison else None
    value["unknown_policy"] = trigger.unknown_policy.value
    value["unavailable_policy"] = trigger.unavailable_policy.value
    return value
