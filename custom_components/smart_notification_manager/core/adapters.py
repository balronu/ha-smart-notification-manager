"""Channel adapter contracts; no adapter sends messages in Phase 1."""

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

