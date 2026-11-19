"""Deterministic, Home-Assistant-independent condition evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from .conditions import TimeWindow
from .rules import Comparison, ConditionNode


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    states: dict[str, str]
    numeric_states: dict[str, float]
    presence: dict[str, bool]
    now: datetime


def evaluate_condition(node: ConditionNode, context: EvaluationContext) -> bool:
    """Evaluate a condition tree with no frontend or HA dependency."""

    if node.kind == "all":
        return bool(node.children) and all(evaluate_condition(child, context) for child in node.children)
    if node.kind == "any":
        return bool(node.children) and any(evaluate_condition(child, context) for child in node.children)
    if node.kind == "entity_state":
        value = node.value
        current = context.states.get(value["entity_id"])
        if current in {None, "unknown", "unavailable"}:
            return False
        return current == value.get("state")
    if node.kind == "numeric":
        value = node.value
        current = context.numeric_states.get(value["entity_id"])
        if current is None:
            return False
        return _compare(current, value["comparison"], float(value["threshold"]), value.get("upper_threshold"))
    if node.kind == "presence":
        return context.presence.get(node.value["entity_id"], False) == bool(node.value.get("present", True))
    if node.kind == "weekday":
        return context.now.weekday() in {int(day) for day in node.value["days"]}
    if node.kind == "time_window":
        start = time.fromisoformat(node.value["start"])
        end = time.fromisoformat(node.value["end"])
        return TimeWindow(start, end).contains(context.now.timetz().replace(tzinfo=None))
    raise ValueError(f"unknown condition kind: {node.kind}")


def _compare(current: float, comparison: str, threshold: float, upper: Any) -> bool:
    if comparison == Comparison.EQ:
        return current == threshold
    if comparison == Comparison.NE:
        return current != threshold
    if comparison == Comparison.GT:
        return current > threshold
    if comparison == Comparison.GTE:
        return current >= threshold
    if comparison == Comparison.LT:
        return current < threshold
    if comparison == Comparison.LTE:
        return current <= threshold
    if comparison == Comparison.BETWEEN:
        return upper is not None and threshold <= current <= float(upper)
    raise ValueError(f"unknown comparison: {comparison}")


def evaluate_state_trigger(
    before: str | None,
    after: str | None,
    *,
    from_state: str | None,
    to_state: str | None,
    elapsed_seconds: float = 0,
    minimum_duration_seconds: float = 0,
) -> bool:
    """Evaluate a state transition, treating unknown values explicitly."""

    if before in {"unknown", "unavailable"} or after in {"unknown", "unavailable"}:
        return False
    if elapsed_seconds < minimum_duration_seconds:
        return False
    if from_state is not None and before != from_state:
        return False
    return to_state is None or after == to_state


def evaluate_numeric_trigger(
    current: float,
    comparison: str,
    threshold: float,
    *,
    upper_threshold: float | None = None,
    previous_match: bool = False,
    hysteresis: float = 0,
    elapsed_seconds: float = 0,
    minimum_duration_seconds: float = 0,
) -> bool:
    """Evaluate numeric thresholds with duration and anti-chatter hysteresis."""

    if elapsed_seconds < minimum_duration_seconds:
        return False
    margin = hysteresis if previous_match else 0
    if comparison in {Comparison.GT, Comparison.GTE}:
        return current > threshold - margin if comparison == Comparison.GT else current >= threshold - margin
    if comparison in {Comparison.LT, Comparison.LTE}:
        return current < threshold + margin if comparison == Comparison.LT else current <= threshold + margin
    return _compare(current, comparison, threshold, upper_threshold)
