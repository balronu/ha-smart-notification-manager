from types import SimpleNamespace

from smart_notification_manager.core import entity_catalog


def test_entity_catalog_uses_entity_device_area_and_state_registries(monkeypatch):
    entity = SimpleNamespace(
        entity_id="sensor.temperature",
        name=None,
        original_name="Temperatur",
        device_id="device-1",
        area_id=None,
        domain="sensor",
    )
    monkeypatch.setattr(entity_catalog.entity_registry, "async_get", lambda hass: SimpleNamespace(entities={"x": entity}))
    monkeypatch.setattr(
        entity_catalog.device_registry,
        "async_get",
        lambda hass: SimpleNamespace(async_get=lambda device_id: SimpleNamespace(area_id="living")),
    )
    monkeypatch.setattr(
        entity_catalog.area_registry,
        "async_get",
        lambda hass: SimpleNamespace(async_get_area=lambda area_id: SimpleNamespace(name="Wohnzimmer")),
    )
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda entity_id: SimpleNamespace(state="21.4")))

    result = entity_catalog.list_entity_snapshots(hass)

    assert result[0].friendly_name == "Temperatur"
    assert result[0].area_name == "Wohnzimmer"
    assert result[0].state == "21.4"
