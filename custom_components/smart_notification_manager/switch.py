"""Rule switches backed by the existing, versioned RuleStore."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .core.permissions import Permission
from .core.rule_store import EditorAccess, rule_to_dict
from .core.rules import Priority


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    runtime = hass.data[DOMAIN]
    rules = await runtime["rule_store"].async_list()
    async_add_entities([RuleSwitch(runtime["rule_store"], runtime["metrics_coordinator"], entry, rule) for rule in rules])


class RuleSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, store, coordinator, entry, rule) -> None:
        super().__init__(coordinator)
        self._store = store
        self._rule = rule
        self._attr_name = f"Regel aktiviert: {rule.name}"
        self._attr_unique_id = f"{entry.entry_id}_rule_{rule.rule_id}"

    @property
    def is_on(self):
        return bool(self._rule.enabled)

    async def async_turn_on(self, **kwargs) -> None:
        await self._save(True)

    async def async_turn_off(self, **kwargs) -> None:
        if self._rule.priority is Priority.CRITICAL:
            raise HomeAssistantError("Critical-Regeln dürfen nur über die geschützte Verwaltung deaktiviert werden.")
        await self._save(False)

    async def _save(self, enabled: bool) -> None:
        value = rule_to_dict(self._rule)
        value["enabled"] = enabled
        value["version"] = self._rule.version + 1
        value["updated_at"] = datetime.now(UTC).isoformat()
        from .core.rule_store import rule_from_editor_payload
        self._rule = await self._store.async_save(rule_from_editor_payload(value), EditorAccess("ha-entity", frozenset({Permission.EDIT.value})))
        self.async_write_ha_state()
