"""Native aggregate sensors for the Smart Notification Manager."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .core.metrics import MetricsCoordinator

SENSORS = (
    ("open_alarms", "Offene Alarme", "open_alarms"),
    ("critical_alarms", "Critical-Alarme", "critical_alarms"),
    ("unacknowledged_alarms", "Nicht quittierte Alarme", "unacknowledged_alarms"),
    ("active_pauses", "Aktive Pausen", "active_pauses"),
    ("delivery_errors", "Zustellfehler", "delivery_errors"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: MetricsCoordinator = hass.data[DOMAIN]["metrics_coordinator"]
    async_add_entities([ManagerSensor(coordinator, entry, key, name, metric) for key, name, metric in SENSORS])


class ManagerSensor(CoordinatorEntity[MetricsCoordinator], SensorEntity):
    _attr_native_unit_of_measurement = "Anzahl"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, key: str, name: str, metric: str) -> None:
        super().__init__(coordinator)
        self._metric = metric
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._metric, 0) if self.coordinator.data else None
