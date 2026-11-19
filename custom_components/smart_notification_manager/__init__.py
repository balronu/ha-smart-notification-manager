"""Smart Notification Manager foundation integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_DB_PATH, DEFAULT_DB_PATH, DOMAIN
from .core.alarm_center import AlarmCenterStore
from .core.alarm_lifecycle import AlarmLifecycleStore
from .core.delivery_service import DeliveryService
from .core.delivery_store import DeliveryStore
from .core.policies import PolicyStore
from .core.recipient_store import RecipientStore
from .core.repository import SQLiteRepository
from .core.rule_store import RuleStore
from .websocket import async_register as async_register_websocket

FRONTEND_URL_BASE = "/smart_notification_manager_static"
FRONTEND_PATH = Path(__file__).parent / "frontend"


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register the domain runtime without creating a productive database."""

    hass.data.setdefault(DOMAIN, {"phase": 2, "recording_enabled": False})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load an entry's non-invasive runtime metadata."""

    runtime = hass.data.setdefault(DOMAIN, {"phase": 2, "recording_enabled": False})
    runtime.setdefault("entries", {})[entry.entry_id] = entry
    options = getattr(entry, "options", {}) or {}
    data = getattr(entry, "data", {}) or {}
    database_path = options.get(CONF_DB_PATH, data.get(CONF_DB_PATH, DEFAULT_DB_PATH))
    if hasattr(hass, "config") and hasattr(hass.config, "path"):
        database_path = hass.config.path(database_path)
    repository = SQLiteRepository(database_path)
    runtime["repository"] = repository
    runtime["rule_store"] = RuleStore(repository)
    runtime["recipient_store"] = RecipientStore(repository)
    runtime["delivery_store"] = DeliveryStore(repository)
    runtime["alarm_store"] = AlarmLifecycleStore(repository)
    runtime["alarm_center_store"] = AlarmCenterStore(repository)
    runtime["policy_store"] = PolicyStore(repository)
    runtime["delivery_service"] = DeliveryService(runtime["delivery_store"], runtime["policy_store"])
    if hasattr(hass, "config"):
        async_register_websocket(hass)
    if getattr(hass, "http", None) is not None and not runtime.get("frontend_registered"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(f"{FRONTEND_URL_BASE}", str(FRONTEND_PATH), cache_headers=False)]
        )
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            webcomponent_name="smart-notification-manager-panel",
            sidebar_title="Benachrichtigungen",
            sidebar_icon="mdi:bell-outline",
            module_url=f"{FRONTEND_URL_BASE}/smart-notification-manager.js",
            embed_iframe=True,
            require_admin=True,
            config_panel_domain=DOMAIN,
        )
        frontend.add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/smart-notification-manager.js?v=2")
        runtime["frontend_registered"] = True
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload only this integration's runtime metadata."""

    runtime = hass.data.get(DOMAIN, {})
    runtime.get("entries", {}).pop(entry.entry_id, None)
    runtime.pop("rule_store", None)
    runtime.pop("recipient_store", None)
    runtime.pop("delivery_store", None)
    runtime.pop("delivery_service", None)
    runtime.pop("alarm_store", None)
    runtime.pop("alarm_center_store", None)
    runtime.pop("policy_store", None)
    runtime.pop("repository", None)
    return True
