"""Minimal German-first Config and Options Flow for the Phase-1 foundation."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_DB_PATH, CONF_LANGUAGE, DEFAULT_DB_PATH, DEFAULT_LANGUAGE, DOMAIN


class SmartNotificationManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create one explicitly configured foundation entry."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        if user_input is not None:
            return self.async_create_entry(title="Smart Notification Manager", data={}, options=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(["de", "en"]),
                    vol.Required(CONF_DB_PATH, default=DEFAULT_DB_PATH): str,
                }
            ),
        )

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SmartNotificationManagerOptionsFlow()


class SmartNotificationManagerOptionsFlow(config_entries.OptionsFlow):
    """Edit only foundation settings; no channel sends are exposed."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LANGUAGE, default=self.config_entry.options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)): vol.In(["de", "en"]),
                    vol.Required(CONF_DB_PATH, default=self.config_entry.options.get(CONF_DB_PATH, DEFAULT_DB_PATH)): str,
                }
            ),
        )

