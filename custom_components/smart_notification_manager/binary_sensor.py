"""Native boolean alarm health entities."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

ENTITIES = (("critical_present", "Critical-Alarm vorhanden", "critical_alarms"), ("open_present", "Offener Alarm vorhanden", "open_alarms"), ("delivery_degraded", "Zustellsystem gestört", "delivery_errors"))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN]["metrics_coordinator"]
    async_add_entities([ManagerBinarySensor(coordinator, entry, key, name, metric) for key, name, metric in ENTITIES])


class ManagerBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, entry, key: str, name: str, metric: str) -> None:
        super().__init__(coordinator)
        self._metric = metric
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def is_on(self):
        return bool(self.coordinator.data and self.coordinator.data.get(self._metric, 0))
