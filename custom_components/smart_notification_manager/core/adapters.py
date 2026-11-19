"""Channel adapter contracts and simulation-only registry for Phase 3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ChannelCapabilities:
    """Capabilities exposed by a channel without coupling the rule engine to HA."""

    channel_type: str
    supports_title: bool = True
    supports_actions: bool = False
    supports_media: bool = False
    supports_feedback: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeliveryRequest:
    """Validated delivery request passed to a future adapter."""

    attempt_id: str
    recipient_id: str
    title: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """Adapter result that can be persisted without provider-specific objects."""

    status: str
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class ChannelAdapter(Protocol):
    """Interface for future Companion-App, Telegram, PBX, TTS and mail adapters."""

    @property
    def capabilities(self) -> ChannelCapabilities: ...

    async def async_validate(self, recipient: dict[str, Any]) -> list[str]: ...

    async def async_send(self, request: DeliveryRequest) -> DeliveryResult:
        """Send one request; implementations are introduced in later phases."""

    async def async_feedback(self, payload: dict[str, Any]) -> dict[str, Any] | None: ...


class AdapterRegistry:
    """Registry that exposes capabilities without creating network clients."""

    def __init__(self) -> None:
        self._adapters: dict[str, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter) -> None:
        channel_type = adapter.capabilities.channel_type
        if channel_type in self._adapters:
            raise ValueError(f"Kanal bereits registriert: {channel_type}")
        self._adapters[channel_type] = adapter

    def capabilities(self) -> tuple[ChannelCapabilities, ...]:
        return tuple(adapter.capabilities for adapter in self._adapters.values())

    def get(self, channel_type: str) -> ChannelAdapter | None:
        return self._adapters.get(channel_type)


@dataclass(frozen=True, slots=True)
class SimulatedAdapter:
    """Test adapter: validates and prepares, but never performs external I/O."""

    channel_type: str
    supports_title: bool = True
    supports_actions: bool = False
    supports_media: bool = False

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(self.channel_type, self.supports_title, self.supports_actions, self.supports_media, False, {"mode": "simulation"})

    async def async_validate(self, recipient: dict[str, Any]) -> list[str]:
        return [] if recipient.get("enabled", True) else ["Empfänger ist deaktiviert"]

    async def async_send(self, request: DeliveryRequest) -> DeliveryResult:
        return DeliveryResult(status="simulated", error_message="Kein echter Versand im Simulationsmodus")

    async def async_feedback(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        return None
