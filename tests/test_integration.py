from inspect import signature

import pytest
from homeassistant.components import panel_custom
from smart_notification_manager import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from smart_notification_manager.const import DOMAIN


class FakeServices:
    def has_service(self, domain, service):
        return False


class FakeHass:
    def __init__(self):
        self.data = {}
        self.services = FakeServices()


class FakeEntry:
    entry_id = "phase1-entry"


@pytest.mark.asyncio
async def test_setup_and_unload_do_not_register_delivery_services():
    hass = FakeHass()
    assert await async_setup(hass, {})
    entry = FakeEntry()
    assert await async_setup_entry(hass, entry)
    assert hass.data[DOMAIN]["recording_enabled"] is False
    assert await async_unload_entry(hass, entry)
    assert entry.entry_id not in hass.data[DOMAIN]["entries"]
    assert not hass.services.has_service(DOMAIN, "send")


@pytest.mark.asyncio
async def test_lifecycle_does_not_initialize_sqlite(tmp_path):
    hass = FakeHass()
    entry = FakeEntry()
    database = tmp_path / "manager.sqlite3"
    entry.data = {"db_path": str(database)}

    assert await async_setup(hass, {})
    assert await async_setup_entry(hass, entry)
    assert not database.exists()
    assert await async_unload_entry(hass, entry)
    assert not database.exists()


def test_panel_registration_uses_current_home_assistant_contract():
    parameters = signature(panel_custom.async_register_panel).parameters
    assert {"hass", "frontend_url_path", "webcomponent_name", "module_url", "require_admin"} <= set(parameters)
