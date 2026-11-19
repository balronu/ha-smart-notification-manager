"""Delivery routing contracts without provider execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """A deterministic route decision suitable for audit and persistence."""

    recipient_ids: tuple[str, ...]
    suppressed: bool = False
    suppression_reason: str | None = None


def deduplicate_recipients(recipient_ids: list[str]) -> RouteDecision:
    """Keep first-seen recipient order and remove exact duplicates only."""

    unique = tuple(dict.fromkeys(recipient_ids))
    return RouteDecision(unique)

