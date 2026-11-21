"""Smart Notification Manager foundation integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_DB_PATH, DEFAULT_DB_PATH, DOMAIN
from .core.alarm_center import AlarmCenterStore
from .core.alarm_lifecycle import AlarmLifecycleStore
from .core.automation_migration import AutomationMigrationStore
from .core.delivery_service import DeliveryService
from .core.delivery_store import DeliveryStore
from .core.metrics import async_get_coordinator
from .core.policies import PolicyStore
from .core.recipient_store import RecipientStore
from .core.repeat_delivery import RepeatEscalationDeliveryPlanner
from .core.repository import SQLiteRepository
from .core.rule_store import RuleStore
from .core.rule_templates import RuleTemplateStore
from .core.statistics import StatisticsStore
from .diagnostics import SmartNotificationManagerDiagnosticsView
from .websocket import async_register as async_register_websocket

FRONTEND_URL_BASE = "/smart_notification_manager_static"
FRONTEND_PATH = Path(__file__).parent / "frontend"
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


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
    runtime["rule_template_store"] = RuleTemplateStore(repository)
    runtime["recipient_store"] = RecipientStore(repository)
    runtime["delivery_store"] = DeliveryStore(repository)
    runtime["alarm_store"] = AlarmLifecycleStore(repository)
    runtime["alarm_center_store"] = AlarmCenterStore(repository)
    runtime["automation_migration_store"] = AutomationMigrationStore(repository)
    runtime["policy_store"] = PolicyStore(repository)
    runtime["delivery_service"] = DeliveryService(runtime["delivery_store"], runtime["policy_store"])
    runtime["repeat_delivery_planner"] = RepeatEscalationDeliveryPlanner(
        runtime["alarm_store"], runtime["delivery_store"], runtime["policy_store"]
    )
    runtime["statistics_store"] = StatisticsStore(repository)
    if hasattr(hass, "config_entries") and hasattr(hass.config_entries, "async_forward_entry_setups"):
        runtime["metrics_coordinator"] = await async_get_coordinator(hass, repository)
        await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor", "switch"])
    if hasattr(hass, "config"):
        async_register_websocket(hass)
    if getattr(hass, "http", None) is not None and not runtime.get("frontend_registered"):
        hass.http.register_view(SmartNotificationManagerDiagnosticsView)
        await hass.http.async_register_static_paths(
            [StaticPathConfig(f"{FRONTEND_URL_BASE}", str(FRONTEND_PATH), cache_headers=False)]
        )
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            webcomponent_name="smart-notification-manager-panel",
            sidebar_title="Benachrichtigungen",
            sidebar_icon="mdi:bell-outline",
            module_url=f"{FRONTEND_URL_BASE}/smart-notification-manager.js?v=10",
            # Keep the panel in the HA shell so native sidebar/mobile navigation remains available.
            embed_iframe=False,
            handle_safe_area=True,
            require_admin=True,
            config_panel_domain=DOMAIN,
        )
        frontend.add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/smart-notification-manager.js?v=10")
        frontend.add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/smart-notification-manager-card.js?v=1")
        frontend.add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/phase-8-rule-wizard.js?v=1")
        frontend.add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/phase-9-automation-migration.js?v=1")
        frontend.add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/smart-notification-manager-observation-card.js?v=1")
        frontend.add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/phase-11-guided-migration.js?v=1")
        runtime["frontend_registered"] = True
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload only this integration's runtime metadata."""

    runtime = hass.data.get(DOMAIN, {})
    if hasattr(hass, "config_entries") and hasattr(hass.config_entries, "async_unload_platforms"):
        await hass.config_entries.async_unload_platforms(entry, ["sensor", "binary_sensor", "switch"])
    runtime.get("entries", {}).pop(entry.entry_id, None)
    runtime.pop("rule_store", None)
    runtime.pop("rule_template_store", None)
    runtime.pop("recipient_store", None)
    runtime.pop("delivery_store", None)
    runtime.pop("delivery_service", None)
    runtime.pop("repeat_delivery_planner", None)
    runtime.pop("statistics_store", None)
    runtime.pop("alarm_store", None)
    runtime.pop("alarm_center_store", None)
    runtime.pop("automation_migration_store", None)
    runtime.pop("policy_store", None)
    runtime.pop("metrics_coordinator", None)
    runtime.pop("repository", None)
    return True
