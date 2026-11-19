"""Capability-aware routing and simulation-only delivery preparation."""

from __future__ import annotations

from dataclasses import dataclass

from .adapters import ChannelCapabilities
from .recipients import ResolvedRecipient


@dataclass(frozen=True, slots=True)
class RouteTarget:
    recipient_id: str
    recipient_name: str
    device_id: str
    device_name: str
    channel_id: str
    channel_type: str
    available: bool
    supported: bool
    reason: str | None = None


def build_routing_preview(
    resolved: tuple[ResolvedRecipient, ...],
    channels: dict[str, ChannelCapabilities],
    *,
    media: bool = False,
    actions: bool = False,
) -> tuple[RouteTarget, ...]:
    """Build a stable preview; this function never invokes an adapter."""

    targets: list[RouteTarget] = []
    for item in resolved:
        capability = channels.get(item.channel_id)
        reason = item.reason
        supported = capability is not None
        if capability is None:
            reason = reason or "Kanal nicht verfügbar"
        elif media and not capability.supports_media:
            supported = False
            reason = "Kanal unterstützt keine Bilder"
        elif actions and not capability.supports_actions:
            supported = False
            reason = "Kanal unterstützt keine Aktionen"
        targets.append(RouteTarget(item.recipient_id, item.recipient_name, item.device_id, item.device_name, item.channel_id, capability.channel_type if capability else "unbekannt", item.available, supported and item.available, reason))
    return tuple(targets)
