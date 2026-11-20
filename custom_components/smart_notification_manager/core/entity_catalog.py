"""Read-only Home Assistant entity/device/area registry adapter."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry, device_registry, entity_registry

from .rules import EntitySnapshot


def list_entity_snapshots(hass: HomeAssistant) -> tuple[EntitySnapshot, ...]:
    """Build editor choices from HA's official registries and state store."""

    entities = entity_registry.async_get(hass)
    devices = device_registry.async_get(hass)
    areas = area_registry.async_get(hass)
    snapshots: list[EntitySnapshot] = []
    for entry in entities.entities.values():
        device = devices.async_get(entry.device_id) if entry.device_id else None
        area_id = entry.area_id or (device.area_id if device else None)
        area = areas.async_get_area(area_id) if area_id else None
        state = hass.states.get(entry.entity_id)
        friendly_name = entry.name or entry.original_name or entry.entity_id
        snapshots.append(
            EntitySnapshot(
                entity_id=entry.entity_id,
                friendly_name=friendly_name,
                area_id=area_id,
                area_name=area.name if area else None,
                entity_type=entry.domain,
                state=state.state if state else None,
            )
        )
    return tuple(sorted(snapshots, key=lambda item: (item.area_name or "", item.friendly_name, item.entity_id)))
