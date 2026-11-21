"""Deterministic, Home-Assistant-independent condition evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from .conditions import TimeWindow
from .rules import Comparison, ConditionNode


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    states: dict[str, str]
    numeric_states: dict[str, float]
    presence: dict[str, bool | str | None]
    now: datetime


def evaluate_condition(node: ConditionNode, context: EvaluationContext) -> bool:
    """Evaluate a condition tree with no frontend or HA dependency."""

    if node.kind == "all":
        return all(evaluate_condition(child, context) for child in node.children)
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
        entity_id = node.value["entity_id"]
        current = context.presence.get(entity_id)
        if entity_id not in context.presence or not isinstance(current, bool):
            return False
        return current == bool(node.value.get("present", True))
    if node.kind == "weekday":
        return context.now.weekday() in {int(day) for day in node.value["days"]}
    if node.kind == "time_window":
        start = time.fromisoformat(node.value["start"])
        end = time.fromisoformat(node.value["end"])
        return TimeWindow(start, end).contains(context.now.timetz().replace(tzinfo=None))
    raise ValueError(f"unknown condition kind: {node.kind}")


def _compare(current: float, comparison: str, threshold: float, upper: Any) -> bool:
    if not math.isfinite(float(current)) or not math.isfinite(float(threshold)):
        return False
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
        return upper is not None and math.isfinite(float(upper)) and threshold <= current <= float(upper)
    raise ValueError(f"unknown comparison: {comparison}")


def evaluate_state_trigger(
    before: str | None,
    after: str | None,
    *,
    from_state: str | None,
    to_state: str | None,
    elapsed_seconds: float = 0,
    minimum_duration_seconds: float = 0,
    unknown_policy: str = "ignore",
    unavailable_policy: str = "ignore",
    state_started_at: datetime | None = None,
    now: datetime | None = None,
    already_triggered: bool = False,
) -> bool:
    """Evaluate a transition or a stable target state after its hold time."""

    if before == "unknown" and unknown_policy != "match":
        return False
    if after == "unknown" and unknown_policy != "match":
        return False
    if before == "unavailable" and unavailable_policy != "match":
        return False
    if after == "unavailable" and unavailable_policy != "match":
        return False
    if before == after and state_started_at is None:
        return False
    if already_triggered:
        return False
    if state_started_at is not None and now is not None:
        elapsed_seconds = max(0.0, (now - state_started_at).total_seconds())
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

    if not math.isfinite(float(current)) or elapsed_seconds < minimum_duration_seconds:
        return False
    margin = hysteresis if previous_match else 0
    if comparison in {Comparison.GT, Comparison.GTE}:
        return current > threshold - margin if comparison == Comparison.GT else current >= threshold - margin
    if comparison in {Comparison.LT, Comparison.LTE}:
        return current < threshold + margin if comparison == Comparison.LT else current <= threshold + margin
    if comparison == Comparison.BETWEEN:
        if upper_threshold is None or not math.isfinite(float(upper_threshold)):
            return False
        return threshold - margin <= current <= float(upper_threshold) + margin
    return _compare(current, comparison, threshold, upper_threshold)
