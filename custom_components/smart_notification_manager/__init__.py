"""Smart Notification Manager foundation integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register the domain runtime without creating a productive database."""

    hass.data.setdefault(DOMAIN, {"phase": 1, "recording_enabled": False})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load an entry's non-invasive runtime metadata."""

    runtime = hass.data.setdefault(DOMAIN, {"phase": 1, "recording_enabled": False})
    runtime.setdefault("entries", {})[entry.entry_id] = entry
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload only this integration's runtime metadata."""

    runtime = hass.data.get(DOMAIN, {})
    runtime.get("entries", {}).pop(entry.entry_id, None)
    return True

