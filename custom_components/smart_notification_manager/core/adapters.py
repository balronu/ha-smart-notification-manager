"""Channel adapter contracts and safe Home-Assistant service adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

SUPPORTED_CHANNEL_TYPES = {
    "notify": {"label": "Home-Assistant Notify", "service_examples": ["notify.send_message", "notify.<name>"], "target_fields": ["entity_id", "target"]},
    "telegram": {"label": "Telegram über Home-Assistant-Dienst", "service_examples": ["telegram_bot.send_message", "notify.<telegram_entity>"], "target_fields": ["chat_id", "entity_id"]},
    "whatsapp": {"label": "WhatsApp über Home-Assistant-Dienst", "service_examples": [], "target_fields": ["target", "entity_id"]},
    "fritzbox": {"label": "FRITZ!Box über Home-Assistant-Dienst", "service_examples": ["fritz.dial"], "target_fields": ["number", "device_id"]},
    "sip_pbx": {"label": "SIP/PBX über Home-Assistant-Dienst", "service_examples": [], "target_fields": ["entity_id", "target"]},
    "tts": {"label": "TTS über Home-Assistant-Dienst", "service_examples": ["tts.speak"], "target_fields": ["media_player_entity_id", "entity_id"]},
    "email": {"label": "E-Mail über Home-Assistant-Dienst", "service_examples": ["smtp.send_message", "notify.<smtp_entity>"], "target_fields": ["entity_id", "target"]},
    "doorbell": {"label": "Klingel über Home-Assistant-Dienst", "service_examples": [], "target_fields": ["entity_id", "target"]},
    "voice_call": {"label": "Sprachanruf über Home-Assistant-Dienst", "service_examples": [], "target_fields": ["entity_id", "target"]},
    "mobile": {"label": "Mobile App über Home-Assistant-Dienst", "service_examples": ["notify.mobile_app_<device>"], "target_fields": ["target", "entity_id"]},
    "mail": {"label": "E-Mail-Alias über Home-Assistant-Dienst", "service_examples": ["notify.<mail_entity>"], "target_fields": ["entity_id", "target"]},
}

SERVICE_DOMAIN_CONTRACTS = {
    "notify": frozenset({"notify"}),
    "mobile": frozenset({"notify"}),
    "telegram": frozenset({"telegram_bot", "notify"}),
    "email": frozenset({"smtp", "notify"}),
    "mail": frozenset({"notify"}),
    "tts": frozenset({"tts"}),
    "fritzbox": frozenset({"fritz"}),
}


def channel_catalog() -> tuple[dict[str, str], ...]:
    """Return supported channel contracts without claiming provider APIs."""

    return tuple({"channel_type": key, "label": value["label"], "mode": "home_assistant_service", "service_examples": value["service_examples"], "target_fields": value["target_fields"]} for key, value in SUPPORTED_CHANNEL_TYPES.items())


def validate_channel_config(channel_type: str, config: dict[str, Any]) -> None:
    """Require a concrete existing HA service for every channel adapter."""

    if channel_type not in SUPPORTED_CHANNEL_TYPES:
        raise ValueError("Unbekannter Kanaltyp; Provider müssen über einen unterstützten HA-Dienst angebunden werden.")
    service = config.get("service")
    if not isinstance(service, str) or service.count(".") != 1:
        raise ValueError("Jeder Kanal benötigt einen vorhandenen Home-Assistant-Dienst domain.service.")
    domain, service_name = service.split(".", 1)
    allowed_domains = SERVICE_DOMAIN_CONTRACTS.get(channel_type)
    if allowed_domains is not None and domain not in allowed_domains:
        allowed = ", ".join(sorted(allowed_domains))
        raise ValueError(f"{channel_type} benötigt einen Dienst aus den Domänen: {allowed}.")
    if channel_type == "fritzbox":
        if service_name != "dial":
            raise ValueError("fritzbox benötigt den Dienst fritz.dial.")
        if not isinstance(config.get("device_id"), str) or not config["device_id"].strip():
            raise ValueError("fritzbox benötigt eine FRITZ!Box device_id.")
        max_ring_seconds = config.get("max_ring_seconds", 15)
        if not isinstance(max_ring_seconds, int) or not 1 <= max_ring_seconds <= 300:
            raise ValueError("fritzbox benötigt max_ring_seconds zwischen 1 und 300.")


class DeliveryAuthorizationError(PermissionError):
    """Raised when a real service call lacks explicit user confirmation."""


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
    delivery_confirmed: bool = False


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


class HAServiceAdapter:
    """Adapter for an existing HA service, never for a proprietary API.

    The delivery coordinator is responsible for the explicit authorization
    boundary. This adapter only translates a validated request to the
    configured Home Assistant service call.
    """

    def __init__(
        self,
        hass: Any,
        *,
        channel_type: str,
        domain: str,
        service: str,
        capabilities: ChannelCapabilities,
        service_data: dict[str, Any] | None = None,
        target_field: str | None = None,
    ) -> None:
        self.hass = hass
        self.channel_type = channel_type
        self.domain = domain
        self.service = service
        self._capabilities = capabilities
        self._service_data = dict(service_data or {})
        self._target_field = target_field

    @property
    def capabilities(self) -> ChannelCapabilities:
        return self._capabilities

    async def async_validate(self, recipient: dict[str, Any]) -> list[str]:
        if not recipient.get("enabled", True):
            return ["Empfänger ist deaktiviert"]
        if not self.hass.services.has_service(self.domain, self.service):
            return ["Der konfigurierte Home-Assistant-Dienst ist nicht verfügbar"]
        if not recipient.get("channel_id"):
            return ["Das Zielgerät besitzt keine Kanal-ID"]
        return []

    async def async_send(self, request: DeliveryRequest) -> DeliveryResult:
        data = dict(self._service_data)
        data.update(request.payload.get("service_data", {}))
        data["message"] = request.message
        target = request.payload.get("recipient_target")
        if self._target_field and target:
            data[self._target_field] = target
        if self._capabilities.supports_title and request.title:
            data.setdefault("title", request.title)
        await self.hass.services.async_call(self.domain, self.service, data, blocking=True)
        return DeliveryResult(status="accepted")

    async def async_feedback(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        return None


class FritzDialAdapter(HAServiceAdapter):
    """Adapter for the documented Home Assistant ``fritz.dial`` action."""

    def __init__(self, hass: Any, *, device_id: str, max_ring_seconds: int) -> None:
        super().__init__(
            hass,
            channel_type="fritzbox",
            domain="fritz",
            service="dial",
            capabilities=ChannelCapabilities(
                "fritzbox",
                supports_title=False,
                metadata={"service": "fritz.dial", "mode": "home_assistant_service", "device_id": device_id},
            ),
            service_data={"device_id": device_id, "max_ring_seconds": max_ring_seconds},
        )

    async def async_send(self, request: DeliveryRequest) -> DeliveryResult:
        number = request.payload.get("recipient_target") or request.payload.get("number")
        if not isinstance(number, str) or not number.strip():
            return DeliveryResult(status="failed", error_code="missing_number", error_message="FRITZ!Box benötigt eine Rufnummer.")
        data = dict(self._service_data)
        data["number"] = number.strip()
        await self.hass.services.async_call(self.domain, self.service, data, blocking=True)
        return DeliveryResult(status="accepted")


def adapter_from_channel(hass: Any, channel: dict[str, Any]) -> HAServiceAdapter:
    """Build an adapter only from an existing, explicitly configured HA service."""

    config = channel.get("config", {})
    validate_channel_config(str(channel.get("channel_type", "")), config)
    service_name = config.get("service")
    if not isinstance(service_name, str) or service_name.count(".") != 1:
        raise ValueError("Kanal benötigt einen Home-Assistant-Dienst domain.service")
    domain, service = service_name.split(".", 1)
    if channel["channel_type"] == "fritzbox":
        return FritzDialAdapter(hass, device_id=config["device_id"], max_ring_seconds=config.get("max_ring_seconds", 15))
    capabilities = ChannelCapabilities(
        channel_type=channel["channel_type"],
        supports_title=bool(config.get("supports_title", True)),
        supports_actions=bool(config.get("supports_actions", False)),
        supports_media=bool(config.get("supports_media", False)),
        supports_feedback=bool(config.get("supports_feedback", False)),
        metadata={"service": service_name, "mode": "home_assistant_service"},
    )
    return HAServiceAdapter(
        hass,
        channel_type=channel["channel_type"],
        domain=domain,
        service=service,
        capabilities=capabilities,
        service_data=config.get("service_data"),
        target_field=config.get("target_field"),
    )


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
