import pytest
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
